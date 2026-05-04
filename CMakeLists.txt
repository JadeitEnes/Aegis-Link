cmake_minimum_required(VERSION 3.20)

project(aegis-link LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)


add_executable(aegis_publisher src/main.cpp)

target_include_directories(aegis_publisher PRIVATE include)

if(WIN32)
     target_link_libraries(aegis_publisher PRIVATE ws2_32) 
endif()
  
