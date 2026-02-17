#include "MG996R.h"

extern TIM_HandleTypeDef htim12;

/* MG996R  */
#define SERVO_MIN_PULSE  500
#define SERVO_MAX_PULSE  2500

void MG996R_Init(void)
{

    /* Power on center */

	  HAL_TIM_PWM_Start(&htim12, TIM_CHANNEL_1); 
    __HAL_TIM_SET_COMPARE(&htim12, TIM_CHANNEL_1, 1500);
}

void MG996R_SetAngle(uint8_t angle)
{
    uint16_t pulse;

    if (angle > 180) angle = 180;

    pulse = SERVO_MIN_PULSE +
           (uint16_t)((SERVO_MAX_PULSE - SERVO_MIN_PULSE) * angle / 180.0f);

    __HAL_TIM_SET_COMPARE(&htim12, TIM_CHANNEL_1, pulse);
}

// Add servo calibration function
void Servo_Calibration(void)
{
    //printf("Starting servo calibration...\n");
    
    // 1. start for min pulse 500us£¬delay for 2 s 
    __HAL_TIM_SET_COMPARE(&htim12, TIM_CHANNEL_1, 500);
    //printf("Setting to 0 degree (500us)\n");
    HAL_Delay(2000);
    
    // 2. mid position 1500us
    __HAL_TIM_SET_COMPARE(&htim12, TIM_CHANNEL_1, 1500);
    //printf("Setting to 90 degree (1500us)\n");
    HAL_Delay(2000);
    
    // 3. max pulse 2500us
    __HAL_TIM_SET_COMPARE(&htim12, TIM_CHANNEL_1, 2500);
    //printf("Setting to 180 degree (2500us)\n");
    HAL_Delay(2000);
    
    // 4. back to the middle
    __HAL_TIM_SET_COMPARE(&htim12, TIM_CHANNEL_1, 1500);
    //printf("Returning to center\n");
    
    //printf("Calibration complete!\n");
}
