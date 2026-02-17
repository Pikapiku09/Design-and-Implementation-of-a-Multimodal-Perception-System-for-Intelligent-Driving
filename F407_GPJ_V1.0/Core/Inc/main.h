/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f4xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define Encoder_L0_Pin GPIO_PIN_0
#define Encoder_L0_GPIO_Port GPIOA
#define Encoder_L1_Pin GPIO_PIN_1
#define Encoder_L1_GPIO_Port GPIOA
#define Encoder_R0_Pin GPIO_PIN_6
#define Encoder_R0_GPIO_Port GPIOA
#define Encoder_R1_Pin GPIO_PIN_7
#define Encoder_R1_GPIO_Port GPIOA
#define BIN1_Pin GPIO_PIN_8
#define BIN1_GPIO_Port GPIOE
#define BIN2_Pin GPIO_PIN_9
#define BIN2_GPIO_Port GPIOE
#define STBY_Pin GPIO_PIN_10
#define STBY_GPIO_Port GPIOE
#define MG_996_PWM_Pin GPIO_PIN_14
#define MG_996_PWM_GPIO_Port GPIOB
#define AIN1_Pin GPIO_PIN_12
#define AIN1_GPIO_Port GPIOD
#define PWMA_Pin GPIO_PIN_13
#define PWMA_GPIO_Port GPIOD
#define AIN2_Pin GPIO_PIN_14
#define AIN2_GPIO_Port GPIOD
#define PWMB_Pin GPIO_PIN_15
#define PWMB_GPIO_Port GPIOD
#define K230_TX_Pin GPIO_PIN_9
#define K230_TX_GPIO_Port GPIOA
#define K230_RX_Pin GPIO_PIN_10
#define K230_RX_GPIO_Port GPIOA

/* USER CODE BEGIN Private defines */

/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
