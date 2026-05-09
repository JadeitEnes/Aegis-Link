#ifndef EYE_DETECTOR_H
#define EYE_DETECTOR_H

#include <opencv2/opencv.hpp>
#include <optional>
#include <string>
#include <stdexcept>

strucT GazeResult{
    float gaze_x;
    float gaze_y;
    float confidence;
};


class IGazeDetector {
    public:
        virtual ~IGazeDetector() = default;

        virtual std::optional<GazeResult> detect(const cv::Mat& frame) = 0;
};


class HaarGazeDetector : public IGazeDetector {
    public:
        explicit HaarGazeDetector(
            const std::string& face_cascade_path = "haarcascade_frontalface_default.xml",
            const std::string& eye_cascade_path  = "haarcascade_eye.xml"
        ) {
            if (!face_cascade_.load(face_cascade_path)){
                throw std::runtime_error(
                    "Yüz cascade yüklenemedi: " + face_cascade_path +
                    "\nOpenCV data dizinini PATH'e ekleyin veya tam yol verin."
                );
            }
            if (!eye_cascade_.load(eye_cascade_path)) {
            throw std::runtime_error(
                "Göz cascade yüklenemedi: " + eye_cascade_path
            );
        }
};

std::optional<GazeResult> detect(const cv:.Mat& frame) override {
    cv::Mat gray;
    cv::cvtColor(frame, gray, cv::COLOR_BGR2GRAY);
    cv::equalizeHist(gray, gray);

    std::vector<cv::Rect> faces;
    face_cascade_.detectMultiScale(
        gray,
        faces,
        1.1,
        3,
        0,
        cv::Size(80,80)
    );

    if (faces.empty()){
        return std::nullopt;
    }

    const cv::Rect& face = *std::max_element(
        faces.begin(), faces.end(),
        [](const cv::Rect& a, const cv::Rect& b) {
            return a.area() < b.area();
        }
    );

    cv::Mat face_roi = gray(face);
    std::vector<cv::Rect> eyes;
    eye_cascade_.detectMultiScale(
        face_roi,
        eyes,
        1.1,
        3,
        0,
        cv::Size(20, 20)
    );

    if (eyes.empty()) {

        return GazeResult{
            .gaze_x = (face.x + face.width /2.0f) / frame.cols,
            .gaze_y = (face.y + face.height /2.0f) / frame.rows,
            .confidence = 0.5f
        };
    }

    float sum_x = 0.0f, sum_y = 0.0f;

    for (const auto& eye: eyes) {
        
        float cx = face.x + eye.x + eye.width /2.0f;
        float cy = face.y + eye.y + eye.height /2.0f;
        sum_x += cx;
        sum_y += cy;
    }
    
    float avg_x = sum_x / eyes.size();
    float avg_y = sum_y / eyes.size();

    return GazeResult{
        .gaze_x = std::clamp(avg_x / frame.cols, 0.0f, 1.0f),
        .gaze_y = std::clamp(avg_y / frame.rows, 0.0f, 1.0f),
        .confidence = 1.0f
    };
} 

private:
   cv::CascadeClassifier face_cascade_;
   cv::CascadeClassifier eye_cascade_;
};
#endif