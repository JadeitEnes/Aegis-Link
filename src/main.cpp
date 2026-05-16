#include "../include/shared_structs.h"
#include "../include/eye_detector.h"
#include "publisher.cpp"
#include <opencv2/opencv.hpp>
#include <iostream>
#include <thread>
#include <chrono>
#include <atomic>
#include <csignal>
#include <memory>


static std::atomic<bool> g_running{true};

void signal_handler(int) {
    g_running = false;
}

class FpsCounter {
    public:
       void tick(){
        auto now = std::chrono::steady_clock::now();
        frames_++;

        if (frames_==1) {
            start_ = now;
            return;
        }

        double elapsed = std::chrono::duration<double>(now - start_).count();
        if (elapsed >= 1.0) {
            fps_ = frames_ / elapsed;
            frames_ = 0;
            start_ = now;
        }
       }
       
       double fps() const { return fps_; }

    private:
     int frames_ = 0;
     double fps_ = 0.0;
     std::chrono::steady_clock::time_point start_;   

};

int main(int argc, char* argv[]) {
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    int camera_index = (argc > 1) ? std::stoi(argv[1]) : 0;

    std::cout << "=== CWE Baslatildi === \n";
    std::cout << "Kamera index: " << camera_index << "\n";

    cv::VideoCapture cap(camera_index, cv::CAP_DSHOW);
    
    if (!cap.isOpened()) {
        std::cerr << " [HATA] Kamera " << camera_index << "acilamadi!\n";
        return 1;
    }

    cap.set(cv::CAP_PROP_FRAME_WIDTH, 640);
    cap.set(cv::CAP_PROP_FRAME_HEIGHT, 480);
    cap.set(cv::CAP_PROP_FPS, 30);
    cap.set(cv::CAP_PROP_BUFFERSIZE, 1);

    double actual_fps = cap.get(cv::CAP_PROP_FPS);
    std::cout << "Kamera cozunurluk: "
    << cap.get (cv::CAP_PROP_FRAME_WIDTH)<< "x"
    << cap.get (cv::CAP_PROP_FRAME_HEIGHT) 
    << "@" << actual_fps << " FPS\n";
    
    std::unique_ptr<IGazeDetector> detector;
    try {
        detector = std::make_unique<HaarGazeDetector>(
            "haarcascade_frontalface_default.xml",
            "haarcascade_eye.xml"
        );
        std::cout << "Dedektör yüklendi: HaarCascade\n";
    } catch (const std::exception& e) {
        std::cerr << "[HATA] " << e.what() << "\n";
        std::cerr << "İpucu: Cascade_Path ortam değişkenini ayarlayın"
         "veya main.cpp içindeki yolları düzenleyin. \n";
         
         return 1;
    }
    
    EyeTrackPublisher pub;
    std::cout << "Shared memory hazır. Kameradan okuma başlıyor...\n\n";

    cv::Mat frame;
    FpsCounter fps_counter;
    uint64_t no_detection_count = 0;
    
    while (g_running) {

        if (!cap.read(frame) || frame.empty()) {
            std::cerr << " [UYARI] Boş kare - kamera bağlantısı kopmuş olabilir. \n";
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            continue;
        }

        fps_counter.tick();

        auto result = detector->detect(frame);

        if (result.has_value()) {
            pub.publish(result->gaze_x, result->gaze_y, result->confidence);
            no_detection_count = 0;
        } else {
            pub.publish(0.5f, 0.5f, 0.0f);
            no_detection_count++;
        }

        if (pub.frame_count() % 60 == 0) {
            if (result.has_value()){
                std::cout
                << "[Frame " << pub.frame_count() << "] "
                << "gaze=(" << result->gaze_x << ", " << result->gaze_y << ") "
                    << "conf=" << result->confidence << " "
                    << "fps=" << fps_counter.fps() << "\n";
            } else {
                std::cout
                    << " [Frame "<< pub.frame_count() << "] "
                    << " tespit yok ("<< no_detection_count<< ") "
                    << "fps=" << fps_counter.fps() << "\n";
            }
        }
    }
    
    std::cout << "\nDurduruluyor...\n";
    cap.release();
    return 0;
}


