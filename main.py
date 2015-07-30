from __future__ import division
import cv2
import time
import math
import random

import robot
from gaze import Gaze

robot.connect()

# set game time limit
game_time = 20

# get into starting position (sitting down, looking up towards person)
robot.robot().wake()
robot.robot().turnHead(pitch = math.radians(-10))

# give robot some time to get to this angle before starting face tracker
time.sleep(0.5)

# start face tracker
robot.robot().trackFace()

# wait a little to let robot find face
time.sleep(0.5)

gaze = Gaze()

gaze.findPersonPitchAdjustment()

# set timer
timeout = time.time() + game_time

# while the time limit isn't reached
while time.time() < timeout:

	gaze.track()

# stop face tracker
robot.robot().stopTrackingFace()

gaze.analyze()

# sit down slowly
robot.robot().rest()