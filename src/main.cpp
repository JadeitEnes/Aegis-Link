#include "../include/shared_structs.h"
#include "publisher.cpp"
#include <iostream>
#include <thread>
#include <chrono>
#include <cmath>

int main() {

    std::cout << "=== Aegis-Link Baslatildi === \n";

    EyeTrackPublisher pub;

    std::cout << "Simulasyon basliyor... (CTRL+C ile durdur) \n\n";

    uint32_t frame_count = 0;

    while (true) {

        double t = frame_count * 0.05;

        float gaze_x = 0.5f + 0.3f * static_cast<float>(std::cos(t));
        float gaze_y = 0.5f + 0.3f * static_cast<float>(std::sin(t));
        float confidence = 0.95f;

        pub.publish(gaze_x, gaze_y, confidence);

        if (frame_count % 60 == 0) {
            std::cout << "[Frame " << frame_count << "] "
            << "gaze=(" << gaze_x << ", " << gaze_y << ") "
            << "conf=" << confidence << "\n";

        }
        
        frame_count++;

        std::this_thread::sleep_for(std::chrono::milliseconds(16));
    }
    return 0;
}