#!/usr/bin/env python
from subprocess import Popen, PIPE
import utils
import os
import glob
import logging
import linuxcnc
import time
import pickle

# gondola flags
GOND_FLAG_TOUCH = 1

log = logging.getLogger('')
log.setLevel(logging.DEBUG)

# create console handler and set level to info
log_format = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(log_format)
log.addHandler(ch)

# create file handler and set to debug
fh = logging.FileHandler('bipod.log')
fh.setFormatter(log_format)
log.addHandler(fh)

log.info("started")

# this should come from .hal
width = 2265 
g54 = { 'x': width/2, 'y': 1050 -200 } # this is where the g54 0,0 point will be
pre_charge_pos = { 'x' : 0, 'y' : -350 + 200, 'z': 8, 'f' : 7000 } # relative to g54
charge_pos = { 'x' : 0, 'y' : -430 + 200, 'z': 8, 'f' : 2000 } # relative to g54

# lengthen strings if necessary
"""
def pre_home_jog():
    log.info("pre home jog")
    jog = 100 #mm
    velocity = 100
    com = linuxcnc.command()
    sta = linuxcnc.stat()
    home_x, home_y = 'TRUE', 'TRUE'
    while home_x == 'TRUE' and home_y == 'TRUE':
        # jog down a bit anyway in case on top of home switches
        if home_x == 'TRUE':
            com.jog(linuxcnc.JOG_INCREMENT, 0, velocity, jog)
        if home_y == 'TRUE':
            com.jog(linuxcnc.JOG_INCREMENT, 1, velocity, jog)
        com.wait_complete() 
        home_x = Popen('halcmd gets home-x', shell=True, stdout=PIPE).stdout.read().strip()
        home_y = Popen('halcmd gets home-y', shell=True, stdout=PIPE).stdout.read().strip()
        log.info("x: %s y: %s" % (home_x, home_y))
"""

def run_program(file):
    log.info("starting program: %s" % file)
    log.debug("changing to auto mode")
    com.mode(linuxcnc.MODE_AUTO)
    com.wait_complete() # wait until mode switch executed
    sta.poll()

    if sta.task_mode == linuxcnc.MODE_AUTO:
        log.debug("success")

    com.program_open(file)
    com.auto(linuxcnc.AUTO_RUN, 0) # second arg is start line
    wait_till_done()



def move_to_precharge():
    log.info("moving to precharge")
    log.debug("changing to auto mode")
    com.mode(linuxcnc.MODE_MDI)
    com.wait_complete() # wait until mode switch executed
    sta.poll()
    if sta.task_mode == linuxcnc.MODE_MDI:
        log.debug("success")

    log.info("sending gcode x%d y%d" % (pre_charge_pos['x'], pre_charge_pos['y']))
    com.mdi("g1 x%d y%d f%d" % (pre_charge_pos['x'], pre_charge_pos['y'], pre_charge_pos['f']))

    wait_till_done()

def move_to_charge():
    log.info("moving back to charging position")
    log.debug("changing to auto mode")
    com.mode(linuxcnc.MODE_MDI)
    com.wait_complete() # wait until mode switch executed
    sta.poll()
    if sta.task_mode == linuxcnc.MODE_MDI:
        log.debug("success")

    log.info("sending gcode x%d y%d" % (charge_pos['x'], charge_pos['y']))
    com.mdi("g1 x%d y%d f%d" % (charge_pos['x'], charge_pos['y'], charge_pos['f']))
    wait_till_done()

def gondola_touched():
    gond_touch = Popen('halcmd getp xbee.gond_touch', shell=True, stdout=PIPE).stdout.read().strip()
    if gond_touch is not None:
        try:
            gond_touch = int(gond_touch)
            if gond_touch > 5:
   #         gond_flags = int(gond_flags)
   #         if gond_flags & GOND_FLAG_TOUCH:
        
                return True
        except ValueError:
            log.warning("got gondola flag %s couldn't convert to int" % gond_flags)

def wait_till_done():
    paused = False
    while True:
        if gondola_touched() and not paused:
            log.warning("gondola touch detected - pausing")
            paused = True
            com.auto(linuxcnc.AUTO_PAUSE)
        elif not gondola_touched() and paused:
            log.warning("gondola touch OK - resuming")
            paused = False
            com.auto(linuxcnc.AUTO_RESUME)
            
        sta.poll()
        error = err.poll()
        if error:
            kind, text = error
            log.warning("error: %s" % text)
        """
        1 EXEC_ERROR
        2  EXEC_DONE
        3  EXEC_WAITING_FOR_MOTION
        4  EXEC_WAITING_FOR_MOTION_QUEUE
        5  EXEC_WAITING_FOR_PAUSE
        6  EXEC_WAITING_FOR_MOTION_AND_IO
        7  EXEC_WAITING_FOR_DELAY
        8  EXEC_WAITING_FOR_SYSTEM_CMD

        2, 3 (not much), 5 or 7 (lots)
        """
        log.debug("exec state %d" % sta.exec_state)

        #1 to 4: INTERP_IDLE, INTERP_READING, INTERP_PAUSED, INTERP_WAITING
        # 1, 2 or 4
        log.debug("interp state %d" % sta.interp_state)

        # RCS_DONE, RCS_EXEC, RCS_ERROR.
        # 1, 2 (mostly) or 3 - worth investigating state 3
        log.debug("state %d" % sta.state)

        #1 to 6: INTERP_OK, INTERP_EXIT, INTERP_EXECUTE_FINISH, INTERP_ENDFILE, INTERP_FILE_NOT_OPEN, INTERP_ERROR 
        # always 0 so far
        log.debug("interp errcode %d" % sta.interpreter_errcode)
        log.debug("line in file %d" % sta.read_line)
        time.sleep(1)
        if sta.interp_state == linuxcnc.INTERP_IDLE:
            log.info("finished")
            break

# Usage examples for some of the commands listed below:
com = linuxcnc.command()
sta = linuxcnc.stat()
err = linuxcnc.error_channel()

com.state(linuxcnc.STATE_ESTOP_RESET)
com.wait_complete() 
com.state(linuxcnc.STATE_ON)
com.wait_complete()

log.info("homing all")
com.home(0)
com.home(1)
com.home(2)

while not sta.homed[0:3] == (1,1,1):
    log.debug("homing...")
    sta.poll()
    time.sleep(1)

##############################

log.info("teleop mode")
com.teleop_enable(1)
com.wait_complete()
# doesn't seem to be a way to check if this worked

###############################

log.info("changing to mdi mode")
com.mode(linuxcnc.MODE_MDI)
com.wait_complete() # wait until mode switch executed
sta.poll()
if sta.task_mode == linuxcnc.MODE_MDI:
    log.debug("success")

log.info("resetting g54 to x%d y%d" % (g54['x'], g54['y']))
com.mdi("g10 l2 p1 x%d y%d" % (g54['x'], g54['y']))
com.feedrate(200)
move_to_precharge()
move_to_charge()

###############################


dir = '/tmp/gcodes/*ngc'
while True:
    files = glob.glob(dir)
    if len(files) == 0:
        log.info("no files, sleeping")
        time.sleep(10)
        continue

    move_to_precharge()
    run_program(files[0])

    os.remove(files[0])
    move_to_precharge()
    move_to_charge()

log.info("done")
