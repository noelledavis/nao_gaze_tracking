from __future__ import division
import time
import math
import random
from robot import robot

class Gaze(object):

    def __init__(self):

        # read object angles from file
        self.object_yaws = []
        self.object_pitches = []

        object_angle_file = open("object_angles.txt")
        for object_angle in object_angle_file:
            yaw, pitch = object_angle.split(', ')
            object_yaws.append(float(yaw))
            object_pitches.append(float(pitch))

        self.confidences = dict.fromkeys(object_yaws, 0)
        self.angle_error = math.radians(15)

        # start writing gaze data to robot memory
        robot().subscribeGaze()

    def updatePersonID(self, debug = False):
        """
        Tries to get people IDs, then if none are retrieved, tries again every 0.5 seconds until it gets some. 
        Stores the first person ID in the list as self.person_id.
        """

        # try to get list of IDs of people looking at robot
        people_ids = robot().getPeopleIDs()
        
        # if robot hasn't gotten any people IDs
        while people_ids is None:

            # wait a little bit, then try again
            time.sleep(0.5)
            people_ids = robot().getPeopleIDs()

        if debug:
            print "Done! About to save the first of these people IDs:", people_ids

        self.person_id = people_ids[0]

    def updateRawPersonGaze():
        """
        Stores person's gaze as a list of yaw (left -, right +) and pitch (up pi, down 0) in radians, respectively.
        Bases gaze on both eye and head angles. Does not compensate for variable robot head position.
        """
        
        self.raw_person_gaze = robot().getRawPersonGaze(self.person_id)

        if self.raw_person_gaze is None:
            self.updatePersonID()

    def gazeOnRobot(self):
        """
        Determines whether the person is looking in the general area of the robot's head.
        Bases this off of the last cached raw gaze values.
        """

        if self.raw_person_gaze is None:
            return False

        yaw_in_range = abs(self.raw_person_gaze_yaw - 0) < math.radians(15)
        pitch_in_range = abs(self.raw_person_gaze_pitch - math.radians(90)) < math.radians(20)
        return (yaw_in_range and pitch_in_range)

    def pitchSumOverTime(self, duration):
        """
        Adds pitch value to a sum every time person looks at robot during the given duration.
        Both this sum and the number of times the sum was added to are member variables.
        """

        timeout = time.time() + duration
        while time.time() < timeout:
            self.updateRawPersonGaze()

            if self.gazeOnRobot():
                # add current pitch to pitch sum
                self.pitch_sum += self.raw_person_gaze_pitch
                self.pitch_count += 1

    def findPersonPitchAdjustment(self):
        """
        Stores the adjustment needed to be made to measured gaze pitch values, which it calculates based on the 
        difference between 90 deg and an average measurement of the person's gaze when looking at the robot's eyes.
        Robot speaks to get straight-on gaze to measure, then filters measurements with gazeOnRobot().
        """

        self.pitch_sum = 0
        self.pitch_count = 0

        self.updatePersonID()

        # get person to look directly at eyes
        robot().say("Hi there! My name is Bobby. What's your name?", block=False)
        self.pitchSumOverTime(4)

        # finish talking
        robot().say("Nice to meet you!", block=False)
        self.pitchSumOverTime(3)

        # list of stalling phrases to try to get person to look at robot
        stalls = [
            "This will be lots of fun!",
            "I Spy is my the best game ever.",
            "I love playing I Spy!",
            "We're going to have so much fun playing.",
            "I Spy is so much fun.",
            "I am so ready to play!"
        ]

        while self.pitch_count < 20:

            random.shuffle(stalls)

            for stall in stalls:

                robot().say(stall, block=False)
                self.pitchSumOverTime(4)

                if self.pitch_count >= 20:
                    break

        control_pitch = self.pitch_sum / self.pitch_count

        # the pitch adjustment we need to make is the difference between (the measured value at 90 degrees) and (90 degrees)
        self.person_pitch_adjustment = control_pitch - math.radians(90)

        print "person_pitch_adjustment:", self.person_pitch_adjustment

        # finish talking
        robot().say("Okay, let's play!")

    def updatePersonGaze(self):
        """
        Saves person's gaze as a list of yaw (left -, right +) and pitch (up pi, down 0) in radians, respectively. 
        Gets gaze from updateRawPersonGaze function, then compensates for variable robot head position and measured pitch inaccuracy.
        """

        self.updateRawPersonGaze()

        if self.raw_person_gaze is None:
           self.person_gaze = None

        else:   
            robot_head_yaw, robot_head_pitch = robot().getHeadAngles()
            
            # compensate for variable robot head angles
            self.person_gaze_yaw = self.raw_person_gaze_yaw - robot_head_yaw # person's left is (-), person's right is (+)
            self.person_gaze_pitch = self.raw_person_gaze_pitch - robot_head_pitch # all the way up is pi, all the way down is 0

            # compensate for measured pitch inaccuracy
            self.person_gaze_pitch += self.person_pitch_adjustment

            self.person_gaze = [self.person_gaze_yaw, self.person_gaze_pitch]

    def updatePersonLocation(self):
        """
        Stores person's head location as a list of x, y (right of robot -, left of robot +), and z coordinates 
        in meters relative to spot between robot's feet.
        """
        
        person_location = robot().getPersonLocation(self.person_id)

        if person_location is None:
            self.updatePersonID()

        else:
            self.robot_person_x, self.robot_person_y, self.robot_person_z = person_location

    def personLookingAtObjects(self):
        """
        Returns whether the person is looking lower than the robot's feet.
        """

        # update and check gaze data
        self.updatePersonGaze()
        if self.person_gaze is None:
            return False

        # update and check location data
        self.updatePersonLocation()
        if self.person_location is None:
            return False

        # threshold angle equals atan of x distance between person + robot divided by person's height
        threshold_angle = math.atan(self.robot_person_x / self.robot_person_z)

        # if person is looking in the area of the objects (gaze pitch < angle to look at robot's feet)
        if self.person_gaze_pitch < threshold_angle:
            return True

        return False

    def getObjectLocation(self, debug = False):
        """
        Returns location of gaze relative to spot between robot's feet as a list of x, y, z in meters and yaw, pitch in radians.
        If the person is not looking near the objects, returns None.
        """

        if not self.personLookingAtObjects():
            return None

        # calculate x distance between robot and object
        person_object_x = self.robot_person_z * math.tan(self.person_gaze_pitch)
        robot_object_x = self.robot_person_x - person_object_x

        # calculate y distance between robot and object (left of robot +, right of robot -)
        person_object_y = person_object_x * math.tan(self.person_gaze_yaw)
        robot_object_y = self.robot_person_y + person_object_y

        # calculate robot head yaw needed to gaze at object
        self.robot_object_yaw = math.atan(robot_object_y / robot_object_x)

        robot_object_z = 0
        self.robot_object_pitch = 0

        if debug:
            print "\tperson gaze:", [math.degrees(angle) for angle in self.person_gaze]
            print "\tperson loc:", self.person_location
            print "\tpers obj x", person_object_x
            print "\tpers obj y", person_object_y

        return [robot_object_x, robot_object_y, robot_object_z, self.robot_object_yaw, self.robot_object_pitch]

    def updateConfidences(self, debug = False):
        """
        Determines which object(s) the person is gazing at and adds to the count for those objects.
        These counts are stored in dictionary self.confidences as {object angle: confidence, ..., object angle: confidence}.
        """

        if not self.robot_object_yaw is None:

            for object_angle in self.confidences:
                
                # if gaze angle is within object_angle_error of the object angle on either side
                if abs(object_angle - self.robot_object_yaw) <= self.angle_error:
                    
                    # add 1 to the confidence for that object
                    self.confidences[object_angle] += 1

                    if debug:
                        print "\t", math.degrees(object_angle),

            if debug:
                print

    def normalizeConfidences(self):
        """
        Divides the confidence (gaze count) for each object by the sum of all objects' gaze counts,
        so that the confidences sum to 100%.
        """

        confidence_sum = sum(self.confidences.values())

        # if we at least got some data
        if confidence_sum != 0:

            for object_angle in self.confidences:
                self.confidences[object_angle] /= confidence_sum

    def guess(self):

        print "Object confidences:", [[round(angle, 3), round(self.confidences[angle] * 100)] for angle in self.confidences]

        max_confidence = max(self.confidences.values()) # or set this to some threshold
        
        # tilt head slightly down so it appears we're looking at the objects
        robot().turnHead(pitch = math.radians(15))

        for object_angle, confidence in self.confidences.iteritems():

            # if we're most confident about that object
            if confidence == max_confidence:
                print "Are you thinking of the object at", object_angle, "radians?"
                print "I'm", round(confidence * 100), "% confident about this."
                robot().turnHead(yaw = object_angle)
                time.sleep(3)