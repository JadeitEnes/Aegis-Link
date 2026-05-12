#include "../include/shared_structs.h"
#include "publisher.cpp"
#include <iostream>
#include <chrono>
#include <thread>
#include <atomic>
#include <csignal>
#include <cmath>
#include <random>

static std::atomic<bool> g_running{true};

void signal_handler(int) {
    g_running = false;
}

class EyeStateSimulator {
public:
    EyeStateSimulator():
       rng_(std::random_device{}()),
       blink_interval_(2.0, 6.0),
       blink_duration_(0.1, 0.4),
    {
       schedule_next_blink(left_);
       schedule_next_blink(right_);
    }

    struct EyeState {
        bool is_open = true;
        double next_event_sec = 0.0;
        bool blink_pending = false;
    };

    void update(double elapsed_sec) {
        update_eye(left_, elapsed_sec);
        update_eye(right_, elapsed_sec);
    }

    float confidence() const {
        if (left_.is_open && right_.is_open) return 1.0f;
        if (!left_.is_open && !right_.is_open) return 0.0f;
        return 0.7f;
    }
private:
    std::mt19937 rng_;
    std::uniform_real_distribution<double> blink_interval_;
    std::uniform_real_distribution<double> blink_duration_;

    EyeState left_;
    EyeState right_;

    void schedule_next_blink(EyeState& eye) {
        eye.next_event_sec = blink_interval_(rng_);
        eye.blink_pending = true;
    }

    void schedule_reopen(EyeState& eye) {
        eye.next_event_sec = blink_duration_(rng_);
        eye.blink_pending = false;
    }

    void update_eye(EyeState& eye, double elapsed_sec) {
        eye.next_event_sec -= elapsed_sec;
        if (eye.next_event_sec > 0.0) return;
    
        if (eye.blink_pending) {
            eye.is_open = false;
            schedule_reopen(eye);
        } 
        
        else {
            eye.is_open = true;
            schedule_next_blink(eye);
        }
    }
};

int main() {
     std::signal(SIGINT, signal_handler);
     std::signal(SIGTERM, signal_handler);

     std::cout << " === Aegis-Link Simülatör Başlatıldı ===\n";
     std::cout << " Blink simülasyonu aktif. CTRL+C ile durdur.\n\n";

     EyeTrackPublisher pub;
     EyeStateSimulator eye_sim;
     
     uint32_t frame_count = 0;

     auto last_tick = std::chrono::steady_clock::now();

     while (g_running) {
        auto now = std::chrono::steady_clock::now();
        double delta = std::chrono::duration<double> (now - last_tick).count();
        last_tick = now;

        double t = frame_count * 0.016;
        float gaze_x = 0.5f + 0.35f * static_cast<float>(std::cos(t * 0.8));
        float gaze_y = 0.5f + 0.25f * static_cast<float>(std::sin(t * 1.1));

        eye_sim.update(delta);
        
        pub.publish_full(
            gaze_x,
            gaze_y,
            eye_sim.confidence(),
            eye_sim.left_open() ? 1 : 0,
            eye_sim.right_open() ? 1 : 0
        );

        frame_count++;

        if (frame_count % 60 == 0) {
            std::cout
            << "[Frame " << frame_count << "] "
            << "gaze=(" << gaze_x << ", " << gaze_y << ") "
            << "L=" << (eye_sim.left_open()  ? "ACIK" : "KAPALI") << " "
            << "R=" << (eye_sim.right_open() ? "ACIK" : "KAPALI") << " "
            << "conf=" << eye_sim.confidence() << "\n";

        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(16));
     }

     std::cout<< "\nDurduruluyor...\n";
    
     return 0;
}