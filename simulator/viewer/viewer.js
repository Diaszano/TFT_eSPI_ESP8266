(function (root) {
  'use strict';
  function frameIndex(index, length) {
    if (!length) return -1;
    return Math.max(0, Math.min(length - 1, index));
  }
  function zoomValue(value) {
    const match = /^(1|2|4|8)x$/.exec(String(value));
    if (!match) throw new Error('unsupported zoom');
    return Number(match[1]);
  }
  function mapPixel(clientX, clientY, zoom, width, height) {
    const x = Math.floor(clientX / zoom), y = Math.floor(clientY / zoom);
    return x >= 0 && y >= 0 && x < width && y < height ? {x, y} : null;
  }
  function rgb565(pixel) {
    const r = (pixel >> 11) & 31, g = (pixel >> 5) & 63, b = pixel & 31;
    const hex = value => value.toString(16).padStart(2, '0');
    return '#' + hex(Math.round(r * 255 / 31)) + hex(Math.round(g * 255 / 63)) + hex(Math.round(b * 255 / 31));
  }
  function rgb565At(bytes, index) {
    if (!bytes || index < 0 || index * 2 + 1 >= bytes.length) throw new Error('pixel outside frame');
    return bytes[index * 2] | (bytes[index * 2 + 1] << 8);
  }
  async function verifyFrameHash(bytes, expected) {
    if (!root.crypto || !root.crypto.subtle || !/^[0-9a-f]{64}$/.test(expected)) return false;
    const digest = await root.crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('') === expected;
  }
  function validManifest(manifest) {
    const profile = manifest && manifest.profile, visible = profile && profile.visible, gram = profile && profile.gram;
    return !!manifest && manifest.schema_version === 1 && manifest.hardware === false &&
      manifest.simulated_timing === false && manifest.simulated_memory === false &&
      typeof manifest.scene_id === 'string' && /^[a-z0-9_]+$/.test(manifest.scene_id) &&
      Number.isInteger(manifest.seed) && manifest.seed >= 0 && manifest.seed <= 0xffffffff &&
      Number.isInteger(manifest.rotation) && manifest.rotation >= 0 && manifest.rotation <= 3 &&
      typeof manifest.simulator_version === 'string' && manifest.simulator_version.length > 0 &&
      typeof manifest.source_sha === 'string' && /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(manifest.source_sha) &&
      /^[0-9a-f]{64}$/.test(manifest.profile_hash || '') && /^[0-9a-f]{64}$/.test(manifest.frame_sha256 || '') &&
      profile.pixel_format === 'RGB565' && visible.width === 240 && visible.height === 240 &&
      gram.width >= visible.width && gram.height >= visible.height &&
      Array.isArray(profile.supported_rotations) && profile.supported_rotations.join(',') === '0,1,2,3';
  }
  function stableJson(value) {
    if (Array.isArray(value)) return '[' + value.map(stableJson).join(',') + ']';
    if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + stableJson(value[key])).join(',') + '}';
    return JSON.stringify(value);
  }
  async function verifyProfileHash(profile, expected) {
    if (!root.crypto || !root.crypto.subtle) return false;
    const bytes = new TextEncoder().encode(stableJson(profile));
    const digest = await root.crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('') === expected;
  }
  function displayStatus(report, result, frameSha, profileHash) {
    const statuses = ['PASS','FAIL','SKIP','INCONCLUSIVE','VISUAL_REVIEW_REQUIRED','UNSUPPORTED','NO_BASELINE','RENDERED'];
    if (report && (report.status === 'PASS' || report.status === 'FAIL') &&
        (report.actual_frame_sha256 !== frameSha || report.actual_profile_hash !== profileHash)) return 'INCONCLUSIVE';
    return report && statuses.includes(report.status) ? report.status :
      (result && statuses.includes(result.status) ? result.status : 'INCONCLUSIVE');
  }
  function differenceAt(report, x, y) {
    const first = report && report.first_difference;
    return first && first.x === x && first.y === y ?
      {expected:first.expected_rgb565, actual:first.actual_rgb565} : null;
  }
  if (typeof module !== 'undefined') module.exports = {frameIndex, zoomValue, mapPixel, rgb565, rgb565At, verifyFrameHash, displayStatus, validManifest, differenceAt};
  if (typeof document === 'undefined') return;
  const $ = id => document.getElementById(id);
  const state = {runs: [], index: -1, run: null, raw: null, report: null};
  function message(error) { $('error').textContent = error || ''; }
  function safePath(name) { return typeof name === 'string' && /^[a-z0-9_-]+$/.test(name); }
  async function loadRuns() {
    try {
      const response = await fetch('/api/runs', {cache:'no-store'});
      if (!response.ok) throw new Error('Unable to list simulator runs (' + response.status + ')');
      const data = await response.json();
      if (!data || data.schema_version !== 1 || !Array.isArray(data.runs)) throw new Error('Malformed run catalog');
      state.runs = data.runs.filter(run => run && safePath(run.id) && typeof run.scene_id === 'string');
      const select = $('scene-list'); select.textContent = '';
      for (const run of state.runs) {
        const option = document.createElement('option'); option.value = run.id;
        option.textContent = run.scene_id + ' — ' + run.id; select.appendChild(option);
      }
      if (!state.runs.length) { $('frame-index').textContent = '0 / 0'; throw new Error('No simulator frames found'); }
      state.index = 0; await showRun();
    } catch (error) { message(error.message); }
  }
  async function artifact(file) {
    const response = await fetch('/runs/' + encodeURIComponent(state.run.id) + '/' + file, {cache:'no-store'});
    if (!response.ok) throw new Error(file + ' unavailable (' + response.status + ')');
    return response;
  }
  async function showRun() {
    state.index = frameIndex(state.index, state.runs.length);
    if (state.index < 0) return;
    state.run = state.runs[state.index]; $('scene-list').value = state.run.id;
    $('frame-index').textContent = (state.index + 1) + ' / ' + state.runs.length;
    message('');
    try {
      const manifestResponse = await artifact('manifest.json');
      const manifest = await manifestResponse.json();
      if (!validManifest(manifest) || !await verifyProfileHash(manifest.profile, manifest.profile_hash)) throw new Error('Invalid simulator manifest or profile checksum');
      const resultResponse = await artifact('result.json');
      const result = await resultResponse.json();
      $('status').textContent = displayStatus(null, result);
      $('metadata').textContent = JSON.stringify({scene_id:manifest.scene_id,rotation:manifest.rotation,seed:manifest.seed,
        source_sha:manifest.source_sha,profile:manifest.profile,frame_sha256:manifest.frame_sha256}, null, 2);
      $('identity').textContent = 'Source ' + manifest.source_sha + ' · profile ' + manifest.profile_hash;
      const rawResponse = await artifact('frame.rgb565'); state.raw = new Uint8Array(await rawResponse.arrayBuffer());
      const width = manifest.profile.visible.width, height = manifest.profile.visible.height;
      if (width !== 240 || height !== 240 || width * height * 2 !== state.raw.length) throw new Error('RGB565 frame dimensions/length mismatch');
      if (!await verifyFrameHash(state.raw, manifest.frame_sha256)) throw new Error('RGB565 frame checksum mismatch');
      const png = await artifact('frame.png'); $('frame').src = URL.createObjectURL(await png.blob());
      state.report = null;
      try { state.report = await (await artifact('report.json')).json(); } catch (_) { /* optional comparison report */ }
      $('status').textContent = displayStatus(state.report, result, manifest.frame_sha256, manifest.profile_hash);
      $('comparison').textContent = state.report ? JSON.stringify({status:state.report.status,
        different_pixels:state.report.different_pixels, first_difference:state.report.first_difference,
        bounding_box:state.report.bounding_box}, null, 2) : 'No comparison report';
      updateView();
    } catch (error) { state.raw = null; $('frame').removeAttribute('src'); message(error.message); $('status').textContent = 'INCONCLUSIVE'; }
  }
  function updateView() {
    const zoom = zoomValue($('zoom').value);
    for (const id of ['frame', 'diff-overlay']) { $(id).style.width = (240 * zoom) + 'px'; $(id).style.height = (240 * zoom) + 'px'; }
    const view = $('view').value, file = view === 'diff' ? 'diff.png' : view === 'expected' ? 'expected.png' : 'frame.png';
    $('diff-overlay').hidden = view !== 'diff';
    if (view === 'candidate' || view === 'diff') artifact('frame.png').then(async r => { $('frame').src = URL.createObjectURL(await r.blob()); }).catch(() => message('Candidate PNG unavailable'));
    if (view === 'diff') artifact(file).then(async r => { $('diff-overlay').src = URL.createObjectURL(await r.blob()); }).catch(() => { $('diff-overlay').hidden = true; message('No difference artifact available'); });
    if (view === 'expected') artifact(file).then(async r => { $('frame').src = URL.createObjectURL(await r.blob()); }).catch(() => message('Expected frame unavailable'));
  }
  $('prev-frame').addEventListener('click', () => { state.index = frameIndex(state.index - 1, state.runs.length); showRun(); });
  $('next-frame').addEventListener('click', () => { state.index = frameIndex(state.index + 1, state.runs.length); showRun(); });
  $('scene-list').addEventListener('change', event => { state.index = state.runs.findIndex(run => run.id === event.target.value); showRun(); });
  $('zoom').addEventListener('change', updateView); $('view').addEventListener('change', updateView);
  $('frame').addEventListener('mousemove', event => {
    if (!state.raw) return;
    const rect = event.currentTarget.getBoundingClientRect(), scale = rect.width / 240;
    const point = mapPixel(event.clientX - rect.left, event.clientY - rect.top, scale, 240, 240);
    if (!point) return;
    const pixel = rgb565At(state.raw, point.y * 240 + point.x);
    let value = 'x=' + point.x + ' y=' + point.y + ' · RGB565 0x' + pixel.toString(16).padStart(4,'0').toUpperCase() + ' · RGB888 ' + rgb565(pixel);
    const diff = differenceAt(state.report, point.x, point.y);
    if (diff) value += ' · expected ' + diff.expected + ' · actual ' + diff.actual;
    $('pixel-info').textContent = value;
  });
  loadRuns();
})(typeof globalThis !== 'undefined' ? globalThis : this);
