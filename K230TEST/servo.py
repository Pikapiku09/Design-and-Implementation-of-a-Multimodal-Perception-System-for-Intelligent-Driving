import time, os, sys
import image
from media.sensor import *
from media.display import *
from media.media import *
from machine import Pin, PWM
from machine import FPIOA

#----------------------Initialize----------------------#
sensor_id = 2
sensor = None

picture_width = 544
picture_height = 288

# Display mode selection
DISPLAY_MODE = "LCD"

# Set display width and height based on mode
if DISPLAY_MODE == "VIRT":
    DISPLAY_WIDTH = ALIGN_UP(1920, 16)
    DISPLAY_HEIGHT = 1080
elif DISPLAY_MODE == "LCD":
    DISPLAY_WIDTH = 800
    DISPLAY_HEIGHT = 480
elif DISPLAY_MODE == "HDMI":
    DISPLAY_WIDTH = 1920
    DISPLAY_HEIGHT = 1080
else:
    raise ValueError("Unknown DISPLAY_MODE")

#----------------------Initialize Servo----------------------#
# Initialize servo control
fpioa = FPIOA()
fpioa.set_function(47, FPIOA.PWM3)
S1 = PWM(3, 50, duty=0, enable=True)

# Servo control parameters
MAX_LEFT_ANGLE = -45
MAX_RIGHT_ANGLE = 45
CENTER_ANGLE = 0
STEP_DELAY = 0.02
ANGLE_STEP = 2

class SteeringControl:
    def __init__(self, servo_pwm):
        self.servo = servo_pwm
        self.current_angle = CENTER_ANGLE
        self.move_to(CENTER_ANGLE)

    def _clamp(self, angle, min_val, max_val):
        return max(min_val, min(angle, max_val))

    def _set_pwm(self, angle):
        duty = (angle + 90) / 180 * 10 + 2.5
        self.servo.duty(duty)

    def move_to(self, target_angle):
        target_angle = self._clamp(target_angle, MAX_LEFT_ANGLE, MAX_RIGHT_ANGLE)

        while abs(self.current_angle - target_angle) > 0.1:
            if self.current_angle < target_angle:
                self.current_angle += ANGLE_STEP
                if self.current_angle > target_angle:
                    self.current_angle = target_angle
            else:
                self.current_angle -= ANGLE_STEP
                if self.current_angle < target_angle:
                    self.current_angle = target_angle

            self._set_pwm(self.current_angle)
            time.sleep(STEP_DELAY)

    def stop(self):
        self.move_to(CENTER_ANGLE)

    def deinit(self):
        self.servo.deinit()

# Instantiate steering control
steering = SteeringControl(S1)

# Lane detection and tracking parameters
last_error = 0
integral = 0
Kp = 0.3  # Proportional gain - adjust based on testing
Kd = 0.1  # Derivative gain - adjust based on testing
Ki = 0.01  # Integral gain - adjust based on testing

def calculate_steering_angle(lines, img_width):
    """Calculate steering angle based on detected lane lines"""
    global last_error, integral

    if not lines:
        # No lines detected, return to center slowly
        return 0

    left_lines = []
    right_lines = []
    image_center = img_width // 2

    # Classify lines as left or right lane based on their position and angle
    for line in lines:
        # Calculate line center
        line_center_x = (line.x1() + line.x2()) // 2

        if line_center_x < image_center:
            left_lines.append(line)
        else:
            right_lines.append(line)

    left_center = None
    right_center = None

    # Calculate average position for left lane lines
    if left_lines:
        left_centers = [(line.x1() + line.x2()) // 2 for line in left_lines]
        left_center = sum(left_centers) / len(left_centers)

    # Calculate average position for right lane lines
    if right_lines:
        right_centers = [(line.x1() + line.x2()) // 2 for line in right_lines]
        right_center = sum(right_centers) / len(right_centers)

    # Calculate target center position
    if left_center is not None and right_center is not None:
        # Both lanes detected - aim for center between them
        target_center = (left_center + right_center) / 2
    elif left_center is not None:
        # Only left lane detected - aim for a fixed offset from it
        target_center = left_center + 100  # Adjust this value based on lane width
    elif right_center is not None:
        # Only right lane detected - aim for a fixed offset from it
        target_center = right_center - 100  # Adjust this value based on lane width
    else:
        # No lines detected
        return 0

    # Calculate error (difference between target center and image center)
    error = image_center - target_center

    # PID control
    integral += error
    derivative = error - last_error
    steering_correction = Kp * error + Ki * integral + Kd * derivative
    last_error = error

    # Convert pixel error to steering angle
    # Adjust this scaling factor based on your needs
    max_pixel_error = img_width // 2
    steering_angle = (steering_correction / max_pixel_error) * MAX_RIGHT_ANGLE

    # Limit steering angle
    steering_angle = max(min(steering_angle, MAX_RIGHT_ANGLE), MAX_LEFT_ANGLE)

    return steering_angle

#----------------------Initialize Camera----------------------#
try:
    # Construct a camera object with default configuration
    sensor = Sensor(id=sensor_id)
    # Reset camera sensor
    sensor.reset()

    # No mirroring or flipping needed
    sensor.set_hmirror(False)
    sensor.set_vflip(False)

    sensor.set_framesize(width=picture_width, height=picture_height, chn=CAM_CHN_ID_0)
    sensor.set_pixformat(Sensor.GRAYSCALE, chn=CAM_CHN_ID_0)

    # Initialize display based on mode
    if DISPLAY_MODE == "VIRT":
        Display.init(Display.VIRT, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, fps=60)
    elif DISPLAY_MODE == "LCD":
        Display.init(Display.ST7701, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, to_ide=True)
    elif DISPLAY_MODE == "HDMI":
        Display.init(Display.LT9611, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, to_ide=True)

    # Initialize media manager
    MediaManager.init()
    # Start sensor
    sensor.run()

    fps = time.clock()
    frame_count = 0
    update_interval = 2  # Update servo every N frames

    while True:
        fps.tick()
        os.exitpoint()
        frame_count += 1

        # Capture image from channel 0
        gray_img = sensor.snapshot(chn=CAM_CHN_ID_0)

        # 1. Define ROI (Region of Interest)
        roi = (100, picture_height // 2, picture_width - 150, picture_height // 2)

        # 2. Canny edge detection
        canny_img = gray_img.find_edges(image.EDGE_CANNY,
                                        threshold=(150, 200),
                                        roi=roi)

        # 3. Hough transform for line detection
        lines = canny_img.find_line_segments(roi=roi,
                                              merge_distance=20,
                                              max_theta_diff=10)

        # 4. Filter and process lines
        filtered_lines = []
        for line in lines:
            # Filter out near-horizontal lines
            if abs(line.theta()) > 20 and abs(line.theta()) < 160:
                filtered_lines.append(line)
                # Draw detected lines
                canny_img.draw_line(line.line(), color=(255, 0, 0), thickness=2)

        # 5. Calculate and apply steering angle
        if frame_count % update_interval == 0:
            steering_angle = calculate_steering_angle(filtered_lines, picture_width)
            steering.move_to(steering_angle)

            # Display steering angle on console
            print(f"Steering Angle: {steering_angle:.1f}°, FPS: {fps.fps():.1f}")

            # Reset frame counter periodically to avoid overflow
            if frame_count > 1000:
                frame_count = 0

        # 6. Display images
        # Display original image
        Display.show_image(gray_img, layer=Display.LAYER_OSD1)
        # Optional: Display edge detection image
        # Display.show_image(canny_img, layer=Display.LAYER_OSD0, x=0, y=200)

except KeyboardInterrupt as e:
    print("User stop: ", e)
except BaseException as e:
    print(f"Exception: {e}")
finally:
    # Stop sensor running
    if isinstance(sensor, Sensor):
        sensor.stop()
    # Return servo to center position
    steering.stop()
    time.sleep(1)
    # Deinitialize servo
    steering.deinit()
    # Deinitialize display module
    Display.deinit()
    os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
    time.sleep_ms(100)
    # Release media buffers
    MediaManager.deinit()
