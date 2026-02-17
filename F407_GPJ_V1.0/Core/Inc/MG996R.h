#ifndef __MG996R_H
#define __MG996R_H

#include "main.h"
#include "tim.h"
/* servo angle of scope */
#define SERVO_MIN_ANGLE     0
#define SERVO_MAX_ANGLE     180

/* PWM pulse(us) */
#define SERVO_MIN_PULSE     500
#define SERVO_MAX_PULSE     2500

void MG996R_Init(void);
void MG996R_SetAngle(uint8_t angle);
void Servo_Calibration(void);
#endif
