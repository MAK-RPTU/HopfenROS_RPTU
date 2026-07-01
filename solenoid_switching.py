#!/usr/bin/env python3
"""
Solenoid Alternating Test
--------------------------
Drives two solenoids (connected to GPIO 23 and GPIO 24 on a Raspberry Pi)
so that they switch ON and OFF alternately, like a two-stroke pump or
oscillating valve.

Process overview:
1. Both solenoids start OFF.
2. The script turns Solenoid 3 ON for a short time, then OFF.
3. Before turning Solenoid 4 ON, it double-checks Solenoid 3 is
   actually OFF (not just commanded off) and waits a short "dead time"
   gap to guarantee there's never a moment where both solenoids are
   energized at the same time.
4. It then turns Solenoid 4 ON for a short time, then OFF.
5. This repeats forever (one full A-then-B cycle = one "period") until
   stopped with Ctrl+C, or until a safety check fails and the script
   shuts both solenoids off automatically.
"""

import RPi.GPIO as GPIO
import time

# ========================= CONFIGURATION =========================

# GPIO pin numbers (BCM numbering) that each solenoid is wired to.
SOLENOID_3 = 23
SOLENOID_4 = 24

# How long one full cycle takes, in seconds (Solenoid 3 ON/OFF +
# Solenoid 4 ON/OFF). Smaller number = faster switching.
# Through testing, 6.5s was found to be the fastest cycle period
# (highest frequency) at which both solenoids still operate reliably.
# Going faster than this risked unreliable/incomplete actuation.
CYCLE_PERIOD = 6.5   # seconds per full cycle (max reliable speed found = 6.5s)

# Mandatory pause (seconds) between switching one solenoid OFF and the
# other ON. This is the safety gap that prevents both solenoids from
# ever being energized at the same time. NEVER change this — safety gap.
DEAD_TIME = 0.05

# ================================================================

# Work out how long each solenoid should stay ON and OFF so that the
# whole cycle (ON + dead time + ON + dead time, for both solenoids)
# adds up to CYCLE_PERIOD.
ON_TIME = (CYCLE_PERIOD - 2 * DEAD_TIME) / 4
OFF_TIME = ON_TIME

# Make sure the chosen CYCLE_PERIOD actually leaves enough time for a
# real ON pulse after accounting for the dead time gaps. If not, stop
# immediately rather than run with a broken/negative timing value.
if ON_TIME <= 0:
    raise ValueError(f"CYCLE_PERIOD {CYCLE_PERIOD}s too short for DEAD_TIME {DEAD_TIME}s")

# --------------------- GPIO INITIALIZATION ------------------------

GPIO.setmode(GPIO.BCM)       # Use Broadcom (BCM) GPIO pin numbering
GPIO.setwarnings(False)      # Suppress "channel already in use" warnings

GPIO.setup(SOLENOID_3, GPIO.OUT)
GPIO.setup(SOLENOID_4, GPIO.OUT)

# Always start with both solenoids OFF, so the system begins in a
# known, safe state.
GPIO.output(SOLENOID_3, GPIO.LOW)
GPIO.output(SOLENOID_4, GPIO.LOW)


def safe_activate(pin_on, pin_off, on_time):
    """
    Turn ON one solenoid (pin_on) while guaranteeing the other solenoid
    (pin_off) is genuinely OFF first.

    Steps:
      1. Command the "other" solenoid OFF and wait DEAD_TIME.
      2. Read back the other solenoid's pin to confirm it's really OFF.
         If it's still reading HIGH, something is wrong (e.g. stuck
         relay/wiring fault) — abort immediately and force both pins
         LOW rather than risk both solenoids being ON together.
      3. Turn the requested solenoid ON, hold it for `on_time` seconds,
         then turn it back OFF and pause for OFF_TIME before returning.
    """
    # Step 1: make sure the other solenoid is commanded off, then wait
    # the safety dead-time gap before doing anything else.
    GPIO.output(pin_off, GPIO.LOW)
    time.sleep(DEAD_TIME)

    # Step 2: verify the other solenoid is actually off (not just
    # commanded off). If it's still HIGH, that's a safety fault.
    if GPIO.input(pin_off) == GPIO.HIGH:
        print(f"SAFETY FAULT: GPIO{pin_off} still HIGH — aborting!")
        GPIO.output(SOLENOID_3, GPIO.LOW)
        GPIO.output(SOLENOID_4, GPIO.LOW)
        raise RuntimeError("Safety fault: both solenoids would be ON")

    # Step 3: it's now safe to energize this solenoid for its ON time,
    # then switch it off and pause before the next call.
    GPIO.output(pin_on, GPIO.HIGH)
    time.sleep(on_time)
    GPIO.output(pin_on, GPIO.LOW)
    time.sleep(OFF_TIME)


# ----------------------------- INFO --------------------------------

print("=== Solenoid Alternating Test ===")
print(f"Cycle period : {CYCLE_PERIOD}s")
print(f"ON time      : {ON_TIME:.4f}s")
print(f"OFF time     : {OFF_TIME:.4f}s")
print(f"Dead time    : {DEAD_TIME}s")
print(f"Frequency    : {1/CYCLE_PERIOD:.3f} Hz")
print("Press Ctrl+C to stop.\n")

# --------------------------- MAIN LOOP ------------------------------

try:
    # Repeat forever: activate Solenoid 3 (safely turning Solenoid 4
    # off first), then activate Solenoid 4 (safely turning Solenoid 3
    # off first). This alternation continues until interrupted.
    while True:
        safe_activate(SOLENOID_3, SOLENOID_4, ON_TIME)
        safe_activate(SOLENOID_4, SOLENOID_3, ON_TIME)

except RuntimeError as e:
    # Triggered by the safety check inside safe_activate().
    print(f"\nSAFETY SHUTDOWN: {e}")

except KeyboardInterrupt:
    # Triggered by the user pressing Ctrl+C.
    print("\nTest stopped.")

finally:
    # Always runs, no matter how the loop exits (safety fault, manual
    # stop, or crash) — guarantees both solenoids end up OFF and GPIO
    # resources are released cleanly.
    GPIO.output(SOLENOID_3, GPIO.LOW)
    GPIO.output(SOLENOID_4, GPIO.LOW)
    GPIO.cleanup()
    print("GPIO cleaned up. Both solenoids OFF.")