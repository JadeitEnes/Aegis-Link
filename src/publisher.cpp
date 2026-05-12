#include "../include/shared_structs.h"
#include <windows.h>
#include <chrono>
#include <iostream>
#include <stdexcept>


#define SHM_FULL_NAME "Local\\aegis_eye_frame"

class EyeTrackPublisher {

private:
    HANDLE         map_handle_;   
    EyeTrackFrame* frame_ptr_;    

public:

    EyeTrackPublisher() {
        map_handle_ = CreateFileMappingA(
            INVALID_HANDLE_VALUE,   
            NULL,                   
            PAGE_READWRITE,         
            0,                      
            sizeof(EyeTrackFrame),  
            SHM_FULL_NAME           
        );

        if (map_handle_ == NULL) {
            throw std::runtime_error("CreateFileMapping basarisiz! Hata kodu: "
                + std::to_string(GetLastError())
            );
        }


        
        frame_ptr_ = static_cast<EyeTrackFrame*>(
            MapViewOfFile(map_handle_, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(EyeTrackFrame))   
        );

        if (frame_ptr_ == NULL) {
            CloseHandle(map_handle_);
            throw std::runtime_error("MapViewOfFile basarisiz! Hata kodu: " +std:.to_string(GetLastError())
           );
        }

        
        ZeroMemory(frame_ptr_, sizeof(EyeTrackFrame));

        std::cout << "[Publisher] Shared memory hazir: "
                  << SHM_FULL_NAME << " ("
                  << sizeof(EyeTrackFrame) << " byte)\n";
    }

    void publish(float gx, float gy, float conf) {
        publish_full(gx, gy, conf, 1, 1);
    }



    void publish_full(float gx, float gy, float conf, uint8_t left_open, uint8_t right_open) {
        frame_ptr_->writer_flag = 1;

        frame_ptr_->gaze_x     = gx;
        frame_ptr_->gaze_y     = gy;
        frame_ptr_->confidence = conf;
        frame_ptr_->left_eye_open = left_open;
        frame_ptr_->right_eye_open = right_open;
        frame_ptr_->frame_id++;

        auto now = std::chrono::steady_clock::now();
        frame_ptr_->timestamps_ns = static_cast<uint64_t>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(
                now.time_since_epoch()
            ).count()
        );

        frame_ptr_->writer_flag = 0;
    }

    uint32_t frame_count() const {
        return frame_ptr_ ? frame_ptr_->frame_id : 0;
    }

    ~EyeTrackPublisher() {
        if (frame_ptr_) UnmapViewOfFile(frame_ptr_);
        if (map_handle_) CloseHandle(map_handle_);
        std::cout << "[Publisher] Shared memory kapatildi.\n";
    }
};