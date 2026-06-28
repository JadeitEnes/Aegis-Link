cmake_minimum_required(VERSION 3.20)

project(CWE LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(OpenCV REQUIRED)
message(STATUS "OpenCV ${OpenCV_VERSION} bulundu: ${OpenCV_DIR}")

add_executable(cwe_simulator src/simulator.cpp)
 
target_include_directories(cwe_simulator PRIVATE include)
 
target_link_libraries(cwe_simulator PRIVATE ws2_32)

add_executable(cwe_publisher src/main.cpp)

target_include_directories(cwe_publisher PRIVATE include ${OpenCV_INCLUDE_DIRS})


target_link_libraries(cwe_publisher PRIVATE ${OpenCV_LIBS} ws2_32)

set(OPENCV_DATA_DIR "${OpenCV_DIR}/../../../share/opencv4/haarcascades")

if (EXISTS "${OPENCV_DATA_DIR}/haarcascade_frontalface_default.xml")
    configure_file(
        "${OPENCV_DATA_DIR}/haarcascade_frontalface_default.xml"
        "${CMAKE_BINARY_DIR}/haarcascade_frontalface_default.xml"
        COPYONLY
    )
    configure_file(
        "${OPENCV_DATA_DIR}/haarcascade_eye.xml"
        "${CMAKE_BINARY_DIR}/haarcascade_eye.xml"
        COPYONLY
    )
    message(STATUS "Cascade dosyalari build dizinine kopyalandi.")
else()
    message(WARNING
        "Cascade dosyalari bulunamadi: ${OPENCV_DATA_DIR}\n"
        "Manuel olarak kopyalayin:\n"
        "  haarcascade_frontalface_default.xml\n"
        "  haarcascade_eye.xml\n"
        " C:/msys64/ucrt64/share/opencv4/haarcascades/"
    )
    
endif()
  
