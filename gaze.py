import time
import math
import random

from naoqi import ALProxy

class Gaze(object):

    def __init__(self):
        # set robot connection values
        IP = 'bobby.local'
        PORT = 9559

        self.memory = ALProxy("ALMemory", IP, PORT)
        self.gaze_analysis = ALProxy("ALGazeAnalysis", IP, PORT)
        self.tts = ALProxy("ALTextToSpeech", IP, PORT)
        self.motion = ALProxy("ALMotion", IP, PORT)

    def updatePersonID(self, debug = False):
        """
        Tries to get people IDs, then if none are retrieved, tries again every 0.5 seconds until it gets some. 
        Stores the first person ID in the list as self.person_id.
        """

        # try to get list of IDs of people looking at robot
        people_ids = self.memory.getData("GazeAnalysis/PeopleLookingAtRobot")
        
        # if robot hasn't gotten any people IDs
        while people_ids is None or len(people_ids) == 0:

            # wait a little bit
            time.sleep(0.5)

            # get list of IDs of people looking at robot
            people_ids = self.memory.getData("GazeAnalysis/PeopleLookingAtRobot")

        if debug:
            print "Done! About to save the first of these people IDs:", people_ids

        self.person_id = people_ids[0]

    def updateRawPersonGaze(self):
        """
        Stores person's gaze a a list of yaw (left -, right +) and pitch (up pi, down 0) in radians, respectively.
        Bases gaze on both eye and head angles. Does not compensate for variable robot head position.
        """

        try:
            # retrieve GazeDirection and HeadAngles values
            gaze_dir = memory.getData("PeoplePerception/Person/" + str(self.person_id) + "/GazeDirection")
            head_angles =  memory.getData("PeoplePerception/Person/" + str(self.person_id) + "/HeadAngles")
            
            # extract gaze direction and head angles data
            person_eye_yaw = gaze_dir[0]
            person_eye_pitch = gaze_dir[1]
            
            person_head_yaw = head_angles[0]
            person_head_pitch = head_angles[1]

        # if gaze data can't be retrieved for that person ID anymore (e.g. if bot entirely loses track of person)
        except RuntimeError:
            # print "Couldn't get gaze direction and head angles for that ID"
            self.raw_person_gaze = None
            self.updatePersonID()

        # if gaze direction or head angles are empty lists (e.g. if person's gaze is too steep)
        except IndexError:
            # print "Gaze data was empty list"
            self.raw_person_gaze = None
            self.updatePersonID()

        else:
            # combine eye and head gaze values
            self.raw_person_gaze_yaw = -(person_eye_yaw + person_head_yaw) # person's left is (-), person's right is (+)
            self.raw_person_gaze_pitch = person_eye_pitch + person_head_pitch + math.pi / 2 # all the way up is pi, all the way down is 0

            self.raw_person_gaze = [self.raw_person_gaze_yaw, self.raw_person_gaze_pitch]

    def gazeOnRobot(self):
        """
        Determines whether the person is looking in the general area of the robot's head.
        Bases this off of the last cached raw gaze values.
        """

        yaw_in_range = abs(self.person_gaze_yaw - 0) < math.radians(15)
        pitch_in_range = abs(self.person_gaze_pitch - math.radians(90)) < math.radians(20)
        return (yaw_in_range and pitch_in_range)

    def findPersonGazePitchAdjustment(self):
        """
        Stores the adjustment needed to be made to measured gaze pitch values based on the difference 
        between 90 deg and an average measurement when the person is looking straight at the robot.
        Robot gets straight-on gaze to measure by speaking, then filters measurements with gazeOnRobot().
        """

        pitch_sum = 0
        pitch_count = 0

        # get person to look directly at eyes
        self.tts.post.say("Hi there! My name is Bobby. What's your name?")

        timeout = time.time() + 4
        while time.time() < timeout:
            self.updateRawPersonGaze()

            if not self.raw_person_gaze is None:
                if self.gazeOnRobot():
                    # add current pitch to pitch sum
                    pitch_sum += self.raw_person_gaze_pitch
                    pitch_count += 1

        # finish talking
        self.tts.post.say("Nice to meet you!")

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
                print pitch_count

                self.tts.post.say(stall)
                print "done giving talking command!"

                # try to get gaze readings for 4 seconds after issuing tts command
                timeout = time.time() + 4
                while time.time() < timeout:
                    
                    self.updateRawPersonGaze()

                    if not self.raw_person_gaze is None:
                        if gazeOnRobot(person_gaze):
                            # add current pitch to pitch sum
                            pitch_sum += self.raw_person_gaze_pitch
                            pitch_count += 1

                    else:
                        self.updatePersonID()

                if pitch_count >= 20:
                    break

        control_pitch = pitch_sum / pitch_count

        # the pitch adjustment we need to make is the difference between (the measured value at 90 degrees) and (90 degrees)
        self.person_gaze_pitch_adjustment = control_pitch - math.radians(90)

        # finish talking
        self.tts.say("Okay, let's play!")

    def getRobotHeadAngles(self):
        """
        Returns current robot head angles as a list of yaw, pitch.
        For yaw, from the robot's POV, left is positive and right is negative. For pitch, up is positive and down is negative.
        See http://doc.aldebaran.com/2-1/family/robots/joints_robot.html for info on the range of its yaw and pitch.
        """

        robot_head_angles = self.motion.getAngles("Head", False)
        robot_head_yaw = robot_head_angles[0]
        robot_head_pitch = -robot_head_angles[1]

        # return adjusted robot head angles
        return [robot_head_yaw, robot_head_pitch]

    def getPersonGaze(self):
        """
        Returns and saves person's gaze as a list of yaw (left -, right +) and pitch (up pi, down 0) in radians, respectively. 
        Gets gaze from updateRawPersonGaze function, then compensates for variable robot head position and measured pitch inaccuracy.
        """

        self.updateRawPersonGaze()

        if self.raw_person_gaze is None:
            return None

        robot_head_yaw, robot_head_pitch = getRobotHeadAngles()
        
        # compensate for variable robot head angles
        self.person_gaze_yaw -= robot_head_yaw # person's left is (-), person's right is (+)
        self.person_gaze_pitch -= robot_head_pitch # all the way up is pi, all the way down is 0

        # compensate for measured pitch inaccuracy
        self.person_gaze_pitch += person_gaze_pitch_adjustment

        return [self.person_gaze_yaw, self.person_gaze_pitch]

    def updatePersonLocation(self):
        """
        Stores person's head location as a list of x, y (right of robot -, left of robot +), and z coordinates 
        in meters relative to spot between robot's feet.
        """
        
        try:
            self.robot_person_loc = self.memory.getData("PeoplePerception/Person/" + str(self.person_id) + "/PositionInRobotFrame")
            self.robot_person_x, self.robot_person_y, self.robot_person_z = self.robot_person_loc

        except RuntimeError:
            # print "Couldn't get person's face location"
            self.person_head_loc = None
            self.updatePersonID()

    def personLookingAtObjects(self):
        """
        Returns whether the person is looking lower than the robot's feet.
        """

        # threshold angle equals atan of x distance between person + robot over person's height
        threshold_angle = math.atan(self.robot_person_x / self.robot_person_z)

        # if person is looking lower than straight ahead (gaze pitch < angle to look at robot's feet)
        if self.person_gaze_pitch < threshold_angle:
            return True

        return False

    def getObjectLocation(debug = False):
        """
        Returns object location relative to spot between robot's feet as a list of x, y, z in meters and yaw, pitch in radians.
        If the person is not looking near the objects, returns None.
        """

        self.updatePersonLocation()
        self.updateRawPersonGaze()

        if not self.personLookingAtObjects():
            return None

        # calculate x distance between robot and object
        person_object_x = self.robot_person_z * math.tan(self.person_gaze_pitch)
        # person_object_x = 0.8
        robot_object_x = self.robot_person_x - person_object_x
        # robot_object_x = 0.5

        # calculate y distance between robot and object (left of robot +, right of robot -)
        person_object_y = person_object_x * math.tan(self.person_gaze_yaw)
        robot_object_y = self.robot_person_y + person_object_y

        # calculate robot head yaw needed to gaze at object
        robot_object_yaw = math.atan(robot_object_y / robot_object_x)

        robot_object_z = 0
        robot_object_pitch = 0

        if debug:
            print "\tperson gaze:", [math.degrees(angle) for angle in self.person_gaze]
            print "\tperson loc:", person_location
            print "\tpers obj x", person_object_x
            print "\tpers obj y", person_object_y

        return [self.robot_object_x, self.robot_object_y, self.robot_object_z, robot_object_yaw, robot_object_pitch]