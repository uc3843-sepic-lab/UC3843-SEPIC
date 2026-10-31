# STM32 supervisory firmware

**Authors: put the firmware here before making the repository public, then delete this note.** This folder is empty on
purpose.

What to add:

1. In STM32CubeIDE, right-click the project → Export → General → Archive File, or copy
   the project folder. Include the `.ioc` file, `Core/` (`main.c` and the supervisory
   routine), and the project files. Leave out `Debug/` and `Release/` build folders.
2. State the firmware values used in the experiments in this README, as the article
   (Section 3.2, Eqs. (1)-(3)) needs them too:
   * moving-average length N_f = ...
   * sign-persistence length N_p = ...
   * command bounds u_min = 5 %, u_max = 93 %, initial command u_0 = 20 %
   * Δu_fine = 0.5 %, Δu_coarse = 2.5 %, P_th = 5 % of nominal unshaded power, P_db = 0.1 P_th
3. Describe what the firmware does when the command reaches a bound and when the power
   change is inside the deadband; the description in Section 3.2 of the article (Eqs. (1)-(3)) should match the code.

Hardware: STM32 Nucleo-F411RE; PWM bias on PA8 (TIM1_CH1, about 20 kHz); INA238 on
I2C1 (PB8 = SCL, PB9 = SDA); logging over USART2 (ST-LINK virtual COM port); 50 ms
supervisory period from a timer interrupt.
