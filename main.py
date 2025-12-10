#!/usr/bin/env python3

from src.cli import main_menu

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye! 👋")
