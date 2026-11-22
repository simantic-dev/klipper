#!/bin/sh
# Build Klipper for STM32F446 (USART2 PA3/PA2, 8 MHz HSE, 250000 baud) into ../out/klipper.elf
set -e
cd "$(dirname "$0")/.."
rm -rf out
cp sim/k446.config .config
# CPP override: macOS `cpp` cannot preprocess the .lds.S; olddefconfig must run before `make` creates out/board
# GNU Make >= 4 needed: macOS make 3.81 links out/board to src/ (empty CONFIG_BOARD_DIRECTORY)
MAKE=$(command -v gmake || echo make)
$MAKE olddefconfig
$MAKE -j4 CPP=arm-none-eabi-cpp
arm-none-eabi-size out/klipper.elf
