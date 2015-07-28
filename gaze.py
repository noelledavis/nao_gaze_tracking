import time
import math
import random

from naoqi import ALProxy
from naoqi import ALBroker

# set robot connection values
IP = 'bobby.local'
PORT = 9559

memory = ALProxy("ALMemory", IP, PORT)
gaze_analysis = ALProxy("ALGazeAnalysis", IP, PORT)
tts = ALProxy("ALTextToSpeech", IP, PORT)
motion = ALProxy("ALMotion", IP, PORT)

def getPersonID(debug = False):
	"""
    Tries to get people IDs, then if none are retrieved, tries again every 0.5 seconds until it gets some. 
	Returns the first person ID in the list.
    """

	# try to get list of IDs of people looking at robot
	people_ids = memory.getData("GazeAnalysis/PeopleLookingAtRobot")
	
	# if robot hasn't gotten any people IDs
	while people_ids is None or len(people_ids) == 0:

		# wait a little bit
		time.sleep(0.5)

		# get list of IDs of people looking at robot
		people_ids = memory.getData("GazeAnalysis/PeopleLookingAtRobot")

	if debug:
		print "Done! About to return the first of these people IDs:", people_ids

	return people_ids[0]

def getRawPersonGaze(person_id):
	"""
    Returns person's gaze a a list of yaw (left -, right +) and pitch (up pi, down 0) in radians, respectively.
	Bases gaze on both eye and head angles. Does not compensate for variable robot head position.
    """

	try:
		# retrieve GazeDirection and HeadAngles values
		gaze_dir = memory.getData("PeoplePerception/Person/" + str(person_id) + "/GazeDirection")
		head_angles =  memory.getData("PeoplePerception/Person/" + str(person_id) + "/HeadAngles")
		
		# extract gaze direction and head angles data
		person_eye_yaw = gaze_dir[0]
		person_eye_pitch = gaze_dir[1]
		
		person_head_yaw = head_angles[0]
		person_head_pitch = head_angles[1]

	# if gaze data can't be retrieved for that person ID anymore (e.g. if bot entirely loses track of person)
	except RuntimeError:
		print "Couldn't get gaze direction and head angles for that ID"
		
		# get new people IDs
		person_id = getPersonID()

		return None

	# if gaze direction or head angles are empty lists (e.g. if person's gaze is too steep)
	except IndexError:
		print "Gaze data was empty list"

		return None

	else:
		# combine eye and head gaze values
		person_gaze_yaw = -(person_eye_yaw + person_head_yaw) # person's left is (-), person's right is (+)
		person_gaze_pitch = person_eye_pitch + person_head_pitch + math.pi / 2 # all the way up is pi, all the way down is 0

		return [person_gaze_yaw, person_gaze_pitch]

def gazeOnRobot(raw_person_gaze):
    """
    Determines whether the person is looking in the general area of the robot's head.
    Bases this purely off of raw gaze values.
    """

    person_gaze_yaw, person_gaze_pitch = raw_person_gaze
    yaw_in_range = abs(person_gaze_yaw - 0) < math.radians(15)
    pitch_in_range = abs(person_gaze_pitch - math.radians(90)) < math.radians(20)
    return yaw_in_range and pitch_in_range

def getPersonGazePitchAdjustment(person_id):
	"""
    Returns the adjustment needed to be made to measured gaze pitch values based on the difference 
    between 90 deg and an average measurement when the person is looking straight at the robot.
    Robot gets straight-on gaze to measure by speaking, then filters measurements with gazeOnRobot().
    """

	pitch_sum = 0
	pitch_count = 0

	# get person to look directly at eyes
	tts.post.say("Hi there! My name is Bobby. What's your name?")

	timeout = time.time() + 4
	while time.time() < timeout:
		person_gaze = getRawPersonGaze(person_id)

		if not person_gaze is None:
			if gazeOnRobot(person_gaze):
                # add current pitch to pitch sum
				pitch_sum += person_gaze[1]
				pitch_count += 1

	# finish talking
	tts.post.say("Nice to meet you!")

	# list of stalling phrases to try to get person to look at robot
	stalls = [
        "This will be lots of fun!",
		"I Spy is my favorite game ever.",
		"I love playing I Spy!",
		"We're going to have so much fun playing.",
		"I Spy is so much fun."
        "I am so ready to play!"
    ]

    while pitch_count < 20:

        random.shuffle(stalls)

    	for stall in stalls:

    		tts.post.say(stall)
    		print "done giving talking command!"

            # try to get gaze readings for 4 seconds after issuing tts command
            timeout = time.time() + 4
            while time.time() < timeout:
                
                person_gaze = getRawPersonGaze(person_id)

                if not person_gaze is None:

                    if gazeOnRobot(person_gaze):

                        # add current pitch to pitch sum
                        pitch_sum += person_gaze[1]
                        pitch_count += 1

            if pitch_count >= 20:
                break

    control_pitch = pitch_sum / pitch_count

	# the pitch adjustment we need to make is the difference between (the measured value at 90 degrees) and (90 degrees)
	person_gaze_pitch_adjustment = control_pitch - math.radians(90)

	return person_gaze_pitch_adjustment

def getRobotHeadAngles():

	# retrieve robot head angles
	robot_head_angles = motion.getAngles("Head", False)

	# unpack robot head angles
	robot_head_yaw = robot_head_angles[0] # left (+) and right (-)
	robot_head_pitch = -robot_head_angles[1] # all the way up (+) and all the way down (-), see http://doc.aldebaran.com/2-1/family/robots/joints_robot.html

	# return adjusted robot head angles
	return [robot_head_yaw, robot_head_pitch]

def getPersonGaze(person_id, person_gaze_pitch_adjustment):
	"""
    Returns person's gaze as a list of yaw (left -, right +) and pitch (up pi, down 0) in radians, respectively. 
	Gets gaze from getRawPersonGaze function, then compensates for variable robot head position and measured pitch inaccuracy.
    """

	person_gaze = getRawPersonGaze(person_id)

	if person_gaze is None:
		return None

	person_gaze_yaw, person_gaze_pitch = person_gaze
	robot_head_yaw, robot_head_pitch = getRobotHeadAngles()
	
	# compensate for variable robot head angles
	person_gaze_yaw -= robot_head_yaw # person's left is (-), person's right is (+)
	person_gaze_pitch -= robot_head_pitch # all the way up is pi, all the way down is 0

	# compensate for measured pitch inaccuracy
	person_gaze_pitch += person_gaze_pitch_adjustment

	return [person_gaze_yaw, person_gaze_pitch]

def getPersonLocation(person_id):
	"""
    Returns person's location as a list of x, y (right of robot -, left of robot +), and z coordinates 
    in meters relative to spot between robot's feet.
    """
	
	try:
		person_head_loc = memory.getData("PeoplePerception/Person/" + str(person_id) + "/PositionInRobotFrame")

	except RuntimeError:
		print "Couldn't get person's face location"
		return None

	return person_head_loc

def personLookingAtObjects(person_gaze, person_location):

	# threshold angle equals atan of x distance between person + robot over person's height
	threshold_angle = math.atan(person_location[0] / person_location[2])

	# if person is looking lower than straight ahead (gaze pitch < angle to look at robot's feet)
	if person_gaze[1] < threshold_angle:
		return True

	return False

def getObjectLocation(person_gaze, person_location, debug = False):
	"""
    Returns object location relative to spot between robot's feet as a list of x, y, z in meters and yaw, pitch in radians.
    """

	# unpack person gaze data (assuming person is looking at object)
	person_object_yaw = person_gaze[0]
	person_object_pitch = person_gaze[1]

	# unpack person location data relative to robot
	robot_person_x = person_location[0]
	robot_person_y = person_location[1]
	robot_person_z = person_location[2]

	# calculate x distance between robot and object
	person_object_x = robot_person_z * math.tan(person_object_pitch)
	# person_object_x = 0.8
	robot_object_x = robot_person_x - person_object_x
	# robot_object_x = 0.5

	# calculate y distance between robot and object (left of robot +, right of robot -)
	person_object_y = person_object_x * math.tan(person_object_yaw)
	robot_object_y = robot_person_y + person_object_y

	# calculate robot head yaw needed to gaze at object
	robot_object_yaw = math.atan(robot_object_y / robot_object_x)

	robot_object_z = 0
	robot_object_pitch = 0

	if debug:
		print "\tperson gaze:", [math.degrees(angle) for angle in person_gaze]
		print "\tperson loc:", person_location
		print "\tpers obj x", person_object_x
		print "\tpers obj y", person_object_y

	return [robot_object_x, robot_object_y, robot_object_z, robot_object_yaw, robot_object_pitch]