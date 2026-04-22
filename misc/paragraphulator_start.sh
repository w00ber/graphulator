#!/bin/bash

# Source your zsh config to get conda
source "$HOME/.zshrc"

# Add LaTeX to PATH (required for matplotlib LaTeX rendering)
export PATH="/Library/TeX/texbin/pdflatex:$PATH"
export PATH="/Library/TeX/texbin:$PATH"

# Activate and run
conda activate CMT
paragraphulator
