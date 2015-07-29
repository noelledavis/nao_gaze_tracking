from __future__ import division
import math
import time

from naoqi import ALProxy
from naoqi import ALBroker

class Confidence(object):

	def __init__(self, object_angles, angle_error):

		IP = 'bobby.local'
		PORT = 9559

		self.motion = ALProxy("ALMotion", IP, PORT)

		# angles and confidences are stored as {angle: confidence}
		# self.confidences = dict.fromkeys([math.radians(angle) for angle in object_angles], 0)
		self.confidences = dict.fromkeys(object_angles, 0)

		self.angle_error = angle_error

	def update(self, gaze_angle, debug = False):

		for object_angle in self.confidences:

			# print round(object_angle, 2), "-", round(gaze_angle, 2), "<=", round(self.angle_error, 2), '\t', abs(object_angle - gaze_angle) <= self.angle_error

			# if gaze angle is within object_angle_error of the object angle on either side
			if abs(object_angle - gaze_angle) <= self.angle_error:
				
				# add 1 to the confidence for that object
				self.confidences[object_angle] += 1

				if debug:
					print "\t", math.degrees(object_angle),

		if debug:
			print

	def normalize(self):

		confidence_sum = sum(self.confidences.values())

		print "count:", self.confidences.values()

		# if we at least got some data
		if confidence_sum != 0:

			for angle in self.confidences:
				self.confidences[angle] /= confidence_sum

	def guess(self):

		print "Object confidences:", [[round(angle, 3), round(self.confidences[angle] * 100)] for angle in self.confidences]

		max_confidence = max(self.confidences.values()) # or set this to some threshold
		
		self.motion.setAngles("HeadPitch", math.radians(15), 0.2)

		for angle, confidence in self.confidences.iteritems():

			# if we're most confident about that object
			if confidence == max_confidence:
				print "Are you thinking of the object at", angle, "radians?"
				print "I'm", round(confidence * 100), "% confident about this."
				self.motion.setAngles("HeadYaw", angle, 0.2)
				time.sleep(3)