#include "tb6612.h"

// ==================== 外部变量声明 ====================
extern TIM_HandleTypeDef htim4;   // PWM定时器
extern TIM_HandleTypeDef htim2;   // 左电机编码器定时器（根据实际修改）
extern TIM_HandleTypeDef htim3;   // 右电机编码器定时器（根据实际修改）

// ==================== 全局变量定义 ====================
PID_TypeDef PID_Left;
PID_TypeDef PID_Right;
// ==================== 基础驱动函数 ====================

/**
 * @brief  初始化电机驱动
 * @note   设置方向引脚、使能STBY、启动PWM
 */
void TB6612_Init(void)
{
    // 1. 将PWM占空比先强制设为0，确保启动时没有输出
    __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_2, 0);
    __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, 0);
    
    // 2. 启动PWM输出
    HAL_TIM_PWM_Start(&htim4, TIM_CHANNEL_2);  // 左电机PWM
    HAL_TIM_PWM_Start(&htim4, TIM_CHANNEL_4);  // 右电机PWM
    
    // 3. 设置初始方向为前进
    AIN1_1; AIN2_0;  // 左电机前进
    BIN1_1; BIN2_0;  // 右电机前进
    
    // 4. 使能STBY（高电平有效）
    HAL_GPIO_WritePin(GPIOE, STBY_Pin, GPIO_PIN_SET);
}

/**
 * @brief  设置左右电机速度（直接PWM控制，无PID）
 * @param  left_speed: 左电机速度 (-SPEED_MAX ~ SPEED_MAX)
 * @param  right_speed: 右电机速度 (-SPEED_MAX ~ SPEED_MAX)
 */
void TB6612_SetSpeed(int32_t left_speed, int32_t right_speed)
{
    // 限制速度范围
    if (left_speed > SPEED_MAX) left_speed = SPEED_MAX;
    if (left_speed < SPEED_MINI) left_speed = SPEED_MINI;
    if (right_speed > SPEED_MAX) right_speed = SPEED_MAX;
    if (right_speed < SPEED_MINI) right_speed = SPEED_MINI;
    
    // 设置左电机方向和速度
    if (left_speed >= 0) {
        AIN1_1; AIN2_0;  // 前进
    } else {
        AIN1_0; AIN2_1;  // 后退
        left_speed = -left_speed;
    }
    
    // 设置右电机方向和速度
    if (right_speed >= 0) {
        BIN1_1; BIN2_0;  // 前进
    } else {
        BIN1_0; BIN2_1;  // 后退
        right_speed = -right_speed;
    }
    
    // 设置PWM占空比
    __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_2, left_speed);
    __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, right_speed);
}

/**
 * @brief  设置电机方向
 * @param  left_dir: 0-后退, 1-前进
 * @param  right_dir: 0-后退, 1-前进
 */
void TB6612_SetDirection(uint8_t left_dir, uint8_t right_dir)
{
    if (left_dir) {
        AIN1_1; AIN2_0;
    } else {
        AIN1_0; AIN2_1;
    }
    
    if (right_dir) {
        BIN1_1; BIN2_0;
    } else {
        BIN1_0; BIN2_1;
    }
}

/**
 * @brief  停止电机
 */
void TB6612_Stop(void)
{
    __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_2, 0);
    __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, 0);
    AIN1_0; AIN2_0;  // 刹车
    BIN1_0; BIN2_0;
}

// ==================== PID控制函数 ====================

/**
 * @brief  初始化PID参数
 * @param  pid: PID结构体指针
 * @param  kp: 比例系数
 * @param  ki: 积分系数
 * @param  kd: 微分系数
 */
void PID_Init(PID_TypeDef *pid, float kp, float ki, float kd)
{
    pid->Kp = kp;
    pid->Ki = ki;
    pid->Kd = kd;
    
    pid->target = 0;
    pid->actual = 0;
    pid->error = 0;
    pid->last_error = 0;
    pid->prev_error = 0;
    pid->integral = 0;
    pid->output = 0;
    
    // 积分限幅（防止积分饱和）
    pid->integral_limit = SPEED_MAX / 2;
    pid->output_limit = SPEED_MAX;
    
    pid->encoder_count = 0;
    pid->last_count = 0;
    pid->speed_rpm = 0;
    pid->speed_pulse = 0;
}

/**
 * @brief  重置PID状态
 * @param  pid: PID结构体指针
 */
void PID_Reset(PID_TypeDef *pid)
{
    pid->error = 0;
    pid->last_error = 0;
    pid->prev_error = 0;
    pid->integral = 0;
    pid->output = 0;
    pid->encoder_count = 0;
    pid->last_count = 0;
}

/**
 * @brief  位置式PID计算
 * @param  pid: PID结构体指针
 * @param  target: 目标值
 * @param  actual: 实际值
 * @return PID输出值
 * @note   位置式PID: u(k) = Kp*e(k) + Ki*∑e(k) + Kd*(e(k)-e(k-1))
 */
float PID_Calculate_Position(PID_TypeDef *pid, float target, float actual)
{
    pid->target = target;
    pid->actual = actual;
    
    // 计算误差
    pid->error = pid->target - pid->actual;
    
    // 积分项（带限幅）
    pid->integral += pid->error;
    if (pid->integral > pid->integral_limit) {
        pid->integral = pid->integral_limit;
    } else if (pid->integral < -pid->integral_limit) {
        pid->integral = -pid->integral_limit;
    }
    
    // PID计算
    pid->output = pid->Kp * pid->error + 
                  pid->Ki * pid->integral + 
                  pid->Kd * (pid->error - pid->last_error);
    
    // 输出限幅
    if (pid->output > pid->output_limit) {
        pid->output = pid->output_limit;
    } else if (pid->output < -pid->output_limit) {
        pid->output = -pid->output_limit;
    }
    
    // 更新历史误差
    pid->last_error = pid->error;
    
    return pid->output;
}

/**
 * @brief  增量式PID计算
 * @param  pid: PID结构体指针
 * @param  target: 目标值
 * @param  actual: 实际值
 * @return PID输出增量
 * @note   增量式PID: Δu(k) = Kp*(e(k)-e(k-1)) + Ki*e(k) + Kd*(e(k)-2e(k-1)+e(k-2))
 */
float PID_Calculate_Increment(PID_TypeDef *pid, float target, float actual)
{
    pid->target = target;
    pid->actual = actual;
    
    // 计算误差
    pid->error = pid->target - pid->actual;
    
    // 增量式PID计算
    float increment = pid->Kp * (pid->error - pid->last_error) + 
                      pid->Ki * pid->error + 
                      pid->Kd * (pid->error - 2 * pid->last_error + pid->prev_error);
    
    // 累加输出
    pid->output += increment;
    
    // 输出限幅
    if (pid->output > pid->output_limit) {
        pid->output = pid->output_limit;
    } else if (pid->output < -pid->output_limit) {
        pid->output = -pid->output_limit;
    }
    
    // 更新历史误差
    pid->prev_error = pid->last_error;
    pid->last_error = pid->error;
    
    return pid->output;
}

/**
 * @brief  设置PID目标值
 */
void PID_SetTarget(PID_TypeDef *pid, float target)
{
    pid->target = target;
}

// ==================== 编码器相关函数 ====================

/**
 * @brief  初始化编码器
 * @note   需要在CubeMX中配置TIM为Encoder Mode
 */
void Encoder_Init(void)
{
    // 启动编码器模式（需要在CubeMX中配置TIM为Encoder Interface）
    // 左电机编码器 - TIM2
    HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL);
    // 右电机编码器 - TIM3
    HAL_TIM_Encoder_Start(&htim3, TIM_CHANNEL_ALL);
}

/**
 * @brief  获取左电机编码器计数
 * @return 编码器计数值
 */
int32_t Encoder_GetLeft(void)
{
    int32_t count = (int32_t)__HAL_TIM_GET_COUNTER(&htim2);
    return count;
}

/**
 * @brief  获取右电机编码器计数
 * @return 编码器计数值
 */
int32_t Encoder_GetRight(void)
{
    int32_t count = (int32_t)__HAL_TIM_GET_COUNTER(&htim3);
    // 右电机可能需要取反（根据安装方向）
    return -count;
}

/**
 * @brief  清除编码器计数
 */
void Encoder_Clear(void)
{
    __HAL_TIM_SET_COUNTER(&htim2, 0);
    __HAL_TIM_SET_COUNTER(&htim3, 0);
}

// ==================== 速度控制函数 ====================

/**
 * @brief  初始化电机速度PID控制
 * @note   调用此函数前需确保TB6612_Init()和Encoder_Init()已执行
 */
void Motor_SpeedControl_Init(void)
{
    // 初始化编码器
    Encoder_Init();
    
    // 初始化PID参数（根据实际电机特性调整）
    // 这些参数需要根据您的电机和负载进行调试
    // 建议调试顺序：先调Kp，再调Kd，最后调Ki
    
    // 左电机PID参数
    PID_Init(&PID_Left, 2.0f, 0.5f, 1.0f);  // Kp, Ki, Kd
    
    // 右电机PID参数
    PID_Init(&PID_Right, 2.0f, 0.5f, 1.0f); // Kp, Ki, Kd
}

/**
 * @brief  设置目标速度
 * @param  left_target: 左电机目标速度（脉冲/采样周期）
 * @param  right_target: 右电机目标速度（脉冲/采样周期）
 */
void Motor_SetTargetSpeed(int32_t left_target, int32_t right_target)
{
    PID_SetTarget(&PID_Left, (float)left_target);
    PID_SetTarget(&PID_Right, (float)right_target);
}

/**
 * @brief  PID速度更新函数
 * @note   需要在定时器中断中周期性调用（建议10ms）
 */
void Motor_PID_Update(void)
{
    int32_t left_count, right_count;
    int32_t left_speed, right_speed;
    
    // 1. 读取编码器计数
    left_count = Encoder_GetLeft();
    right_count = Encoder_GetRight();
    
    // 2. 计算速度（脉冲/采样周期）
    left_speed = left_count - PID_Left.last_count;
    right_speed = right_count - PID_Right.last_count;
    
    // 3. 保存当前计数
    PID_Left.last_count = left_count;
    PID_Right.last_count = right_count;
    
    // 4. 更新速度值
    PID_Left.speed_pulse = left_speed;
    PID_Right.speed_pulse = right_speed;
    
    // 5. PID计算（使用位置式PID）
    float left_pwm = PID_Calculate_Position(&PID_Left, PID_Left.target, (float)left_speed);
    float right_pwm = PID_Calculate_Position(&PID_Right, PID_Right.target, (float)right_speed);
    
    // 6. 设置电机速度
    TB6612_SetSpeed((int32_t)left_pwm, (int32_t)right_pwm);
}

/**
 * @brief  获取当前速度
 * @param  left_speed: 左电机速度指针
 * @param  right_speed: 右电机速度指针
 */
void Motor_GetSpeed(int32_t *left_speed, int32_t *right_speed)
{
    *left_speed = PID_Left.speed_pulse;
    *right_speed = PID_Right.speed_pulse;
}
