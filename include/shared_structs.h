#ifndef SHARED_STRUCTS_H
#define SHARED_STRUCTS_H

#include <cstdint>

#pragma pack(push, 1)

struct EyeTrackFrame {
    uint64_t timestamps_ns;
    float gaze_x;
    float gaze_y;
    float confidence;
    uint32_t frame_id;
    uint8_t writer_flag;
    uint8_t left_eye_open;
    uint8_t right_eye_open;
    uint8_t _pad;
};

#pragma pack(pop)

#define SHM_NAME "cwe_eye_frame"

#endif
  

