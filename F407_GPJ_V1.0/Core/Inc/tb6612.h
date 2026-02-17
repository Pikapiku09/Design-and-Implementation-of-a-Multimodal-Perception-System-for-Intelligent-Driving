#ifndef __TB6612_H__   
#define __TB6612_H__   

#include "main.h"
#include "stdint.h"
#include "tim.h"
#include "gpio.h"
#include "stdio.h"


// ==================== 引脚定义 ====================
// 根据您的硬件连接修改以下宏定义
 // Set L_motor_dir（ANI1=PD12 high，ANI2=PD14 low）
#define AIN1_1 HAL_GPIO_WritePin(GPIOD, AIN1_Pin, GPIO_PIN_SET);   
#define AIN1_0 HAL_GPIO_WritePin(GPIOD, AIN1_Pin, GPIO_PIN_RESET); 
#define AIN2_0 HAL_GPIO_WritePin(GPIOD, AIN2_Pin, GPIO_PIN_RESET); 
#define AIN2_1 HAL_GPIO_WritePin(GPIOD, AIN2_Pin, GPIO_PIN_SET); 
// Set R_motor_dir（BIN1=PE8 high，BIN2=PE9 low）
#define BIN1_1 HAL_GPIO_WritePin(GPIOE, BIN1_Pin, GPIO_PIN_SET);   
#define BIN1_0 HAL_GPIO_WritePin(GPIOE, BIN1_Pin, GPIO_PIN_RESET);   
#define BIN2_1 HAL_GPIO_WritePin(GPIOE, BIN2_Pin, GPIO_PIN_SET); 
#define BIN2_0 HAL_GPIO_WritePin(GPIOE, BIN2_Pin, GPIO_PIN_RESET); 

// ==================== 速度范围定义 ====================
#define SPEED_MAX      1000    // 最大速度（对应PWM满占空比）
#define SPEED_MINI    -1000    // 最小速度（反向最大）
#define SPEED_DEAD     50      // 死区范围（消除电机不转的低PWM）

// ==================== 编码器定义 ====================
// 根据您的编码器配置修改
#define ENCODER_PPR    1320    // 编码器每转脉冲数（根据实际编码器修改）
#define WHEEL_DIAMETER 65      // 轮子直径(mm)
#define SAMPLE_TIME    10      // PID采样周期(ms)

// ==================== PID参数结构体 ====================
typedef struct {
    float Kp;              // 比例系数
    float Ki;              // 积分系数
    float Kd;              // 微分系数
    
    float target;          // 目标速度
    float actual;          // 实际速度
    float error;           // 当前误差
    float last_error;      // 上次误差
    float prev_error;      // 上上次误差（用于增量式PID）
    float integral;        // 积分累积
    float integral_limit;  // 积分限幅
    float output;          // PID输出
    float output_limit;    // 输出限幅
    
    int32_t encoder_count; // 编码器计数
    int32_t last_count;    // 上次编码器计数
    int32_t speed_rpm;     // 转速(RPM)
    int32_t speed_pulse;   // 脉冲速度(脉冲/采样周期)
} PID_TypeDef;

// ==================== 全局变量定义 ====================
extern PID_TypeDef PID_Left;   // 左电机PID
extern PID_TypeDef PID_Right;  // 右电机PID


// ==================== 函数声明 ====================
// 基础驱动函数
void TB6612_Init(void);
void TB6612_SetSpeed(int32_t left_speed, int32_t right_speed);
void TB6612_SetDirection(uint8_t left_dir, uint8_t right_dir);
void TB6612_Stop(void);

// PID控制函数
void PID_Init(PID_TypeDef *pid, float kp, float ki, float kd);
void PID_Reset(PID_TypeDef *pid);
float PID_Calculate_Position(PID_TypeDef *pid, float target, float actual);
float PID_Calculate_Increment(PID_TypeDef *pid, float target, float actual);
void PID_SetTarget(PID_TypeDef *pid, float target);

// 编码器相关函数
void Encoder_Init(void);
int32_t Encoder_GetLeft(void);
int32_t Encoder_GetRight(void);
void Encoder_Clear(void);

// 速度控制函数
void Motor_SpeedControl_Init(void);
void Motor_SetTargetSpeed(int32_t left_target, int32_t right_target);
void Motor_PID_Update(void);
void Motor_GetSpeed(int32_t *left_speed, int32_t *right_speed);

#endif /* __TB6612_T_H */
