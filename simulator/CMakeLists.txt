cmake_minimum_required(VERSION 3.16)
project(tft_espi_simulator LANGUAGES CXX)

enable_testing()
function(sim_sanitize target)
  target_compile_features(${target} PRIVATE cxx_std_11)
  target_compile_options(${target} PRIVATE -Wall -Wextra -Werror
    -fsanitize=address,undefined -fno-sanitize-recover=all)
  target_link_options(${target} PRIVATE -fsanitize=address,undefined -fno-sanitize-recover=all)
endfunction()

add_executable(sim_bus_trace tests/test_bus_trace.cpp core/SpiTrace.cpp)
target_include_directories(sim_bus_trace PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
sim_sanitize(sim_bus_trace)
add_test(NAME sim_bus_trace COMMAND sim_bus_trace)

set(SIMULATOR_SETUP_DEFINITIONS
  TFT_ESPI_SIMULATOR USER_SETUP_LOADED ST7789_DRIVER TFT_WIDTH=240 TFT_HEIGHT=240
  TFT_MOSI=13 TFT_SCLK=14 TFT_DC=0 TFT_RST=2 SPI_FREQUENCY=40000000
  LOAD_GLCD LOAD_FONT2 LOAD_FONT4)
add_library(sim_production STATIC ../src/TFT_eSPI.cpp native/SimulatorTransport.cpp
  native/compat/Arduino.cpp native/Scenes.cpp
  ../extras/hardware/Audit_Validation/ValidationVisualScenes.cpp
  core/SpiTrace.cpp core/St7789VirtualController.cpp core/Rgb565Frame.cpp)
target_include_directories(sim_production PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/native/compat ${CMAKE_CURRENT_SOURCE_DIR}/native
  ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/../src
  ${CMAKE_CURRENT_SOURCE_DIR}/.. ${CMAKE_CURRENT_SOURCE_DIR}/../extras/hardware/Audit_Validation)
target_compile_definitions(sim_production PUBLIC ${SIMULATOR_SETUP_DEFINITIONS})
target_compile_options(sim_production PRIVATE -Wall -Wextra -Werror
  -Wno-unused-variable
  -fsanitize=address,undefined -fno-sanitize-recover=all)

add_executable(sim_real_transport tests/test_real_transport.cpp)
target_link_libraries(sim_real_transport PRIVATE sim_production)
sim_sanitize(sim_real_transport)
add_test(NAME sim_real_transport COMMAND sim_real_transport)
add_test(NAME sim_init_replay COMMAND sim_real_transport init)

add_executable(sim_st7789 tests/test_st7789.cpp core/St7789VirtualController.cpp
  core/Rgb565Frame.cpp core/SpiTrace.cpp)
target_include_directories(sim_st7789 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_definitions(sim_st7789 PRIVATE SIMULATOR_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")
sim_sanitize(sim_st7789)
add_test(NAME sim_st7789_commands COMMAND sim_st7789)
add_test(NAME sim_st7789_ramwr COMMAND sim_st7789 ramwr)

add_executable(sim_st7789_rotation tests/test_st7789_rotation.cpp
  core/St7789VirtualController.cpp core/Rgb565Frame.cpp core/SpiTrace.cpp)
target_include_directories(sim_st7789_rotation PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
sim_sanitize(sim_st7789_rotation)
add_test(NAME sim_st7789_rotation COMMAND sim_st7789_rotation)

foreach(target sim_scenes sim_production_render sim_shared_visual_cases simulator_runner)
  if(target STREQUAL "simulator_runner")
    add_executable(${target} native/SimulatorMain.cpp)
  elseif(target STREQUAL "sim_scenes")
    add_executable(${target} tests/test_scenes.cpp)
  elseif(target STREQUAL "sim_production_render")
    add_executable(${target} tests/test_production_render.cpp)
  else()
    add_executable(${target} tests/test_shared_visual_cases.cpp)
  endif()
  target_link_libraries(${target} PRIVATE sim_production)
  sim_sanitize(${target})
endforeach()
add_test(NAME sim_scene_registry COMMAND sim_scenes)
add_test(NAME sim_production_render COMMAND sim_production_render)
add_test(NAME sim_shared_visual_cases COMMAND sim_shared_visual_cases)
set_tests_properties(sim_real_transport sim_init_replay sim_st7789_commands
  sim_st7789_ramwr sim_st7789_rotation sim_scene_registry sim_production_render
  sim_shared_visual_cases PROPERTIES TIMEOUT 5)
