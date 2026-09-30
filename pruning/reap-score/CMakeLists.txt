# Builds llama-reap-score against a llama.cpp source checkout.
#   cmake -S pruning/reap-score -B build/reap -DLLAMA_CPP_DIR=path/to/llama.cpp -DGGML_CUDA=ON
#   cmake --build build/reap --config Release -j
cmake_minimum_required(VERSION 3.14)
project(reap-score CXX)

set(LLAMA_CPP_DIR "" CACHE PATH "Path to a llama.cpp source checkout")
if(NOT EXISTS "${LLAMA_CPP_DIR}/CMakeLists.txt")
    message(FATAL_ERROR "Set -DLLAMA_CPP_DIR to a llama.cpp source checkout")
endif()

set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)  # one self-contained executable
set(LLAMA_BUILD_COMMON ON CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_APP OFF CACHE BOOL "" FORCE)
set(LLAMA_CURL OFF CACHE BOOL "" FORCE)
add_subdirectory(${LLAMA_CPP_DIR} llama.cpp)

add_executable(llama-reap-score reap-score.cpp)
target_link_libraries(llama-reap-score PRIVATE llama-common llama ${CMAKE_THREAD_LIBS_INIT})
target_compile_features(llama-reap-score PRIVATE cxx_std_17)
