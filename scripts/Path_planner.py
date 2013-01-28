'''
Path planner for Replicape. Just add paths to 
this and they will be executed as soon as no other 
paths are being executed. 
It's a good idea to stack up maybe five path 
segments, to have a buffer. 

Author: Elias Bakken
email: elias.bakken@gmail.com
Website: http://www.hipstercircuits.com
License: BSD

You can use and change this, but keep this heading :)
'''

import time
import numpy as np  
from threading import Thread
from Pru import Pru

class Path_planner:
    ''' Init the planner '''
    def __init__(self, steppers):
        self.steppers = steppers
        self.pru = Pru()                                # Make the PRU
        self.paths = list()                             # Make a list of paths
        self.running = True                             # Yes, we are running
        self.t = Thread(target=self._do_work)            # Make the thread
        self.t.start()		        

    ''' Set the acceleration used '''
    def set_acceleration(self, acceleration):
        self.acceleration = acceleration

    ''' Add a path segment to the path planner '''        
    def add_path(self, path):
        self.paths.append(path)            
        
    ''' Return the number of paths currently on queue '''
    def nr_of_paths(self):
        return len(self.paths)

    ''' Join the thread '''
    def exit(self):
        self.running = False
        self.t.join()

    ''' This loop pops a path, sends it to the PRU 
    and waits for an event '''
    def _do_work(self):
        while self.running:
            if len(self.paths) > 0:
                path = self.paths.pop(0)                        # Get the last path added
                for axis in path.get_axes():                    # Run through all the axes in the path
                    stepper = self.steppers[axis]               # Get a handle of  the stepper
                    data = self._make_data(path, axis)          # Generate the timing and pin data                         
                    if stepper.has_pru():                       # If this stepper has a PRU associated with it
                        self.pru.add_data(data, stepper.get_pru())   # Add the data to the PRU
                    else:               
                        stepper.add_data(data)                  # If not, let the stepper fix this.     
                for axis in path.get_axes():                    # Run through all the axes in the path
                    self.steppers[axis].go()                         # Make them start performing
                self.pru.go()                                        # Make the PRU go as well
                self.pru.wait_for_event()                            # Wait for the PRU to finish execution 
                print "_do_work done"
            else:
                time.sleep(0.1)                                 # If there is no paths to execute, sleep. 

    ''' Make the data for the PRU or steppers '''
    def _make_data(self, path, axis):        
        vec         = path.get_axis_length(axis)                # Total travel distance
        stepper     = self.steppers[axis]
        num_steps   = int(abs(vec) * stepper.get_steps_pr_meter())   # Number of steps to tick
        step_pin    = stepper.get_step_pin()                    # Get the step pin
        dir_pin     = stepper.get_dir_pin()                     # Get the direction pin

        dir_pin     = 0 if vec < 0 else dir_pin             #  Disable the dir-pin if we are going backwards
               
        delays      = self._calculate_delays(path, axis)        # Make the delays
        pins        = [step_pin | dir_pin, dir_pin]*num_steps   # Make the pin states

        i_steps     = num_steps-len(delays)		                # Find out how many delays are missing
        i_delays    = delays[-1::]*i_steps*2		            # Make the intermediate steps
        delays      += i_delays+delays[::-1]                    # Add the missing delays. These are max_speed

        td          = num_steps*stepper.get_steps_pr_meter()    # Calculate the actual travelled distance
        path.set_travelled_distance(axis, td)                   # Set the travelled distance back in the path 

        return (pins, delays)                                   # return the pin states and the data

    ''' Caluclate the delays for a path vector '''
    def _calculate_delays(self, path, axis):
        s = abs(path.get_axis_length(axis))                     # Get the length of the vector
        ratio = s/path.get_length()    	                        # Calculate the ratio       
        Vm = path.get_max_speed()*ratio				            # The travelling speed in m/s
        a  = self.acceleration*ratio    		                # Accelleration in m/s/s
        ds = 1.0/self.steppers[axis].get_steps_pr_meter()       # Delta S, distance in meters travelled pr step. 
        u  = ratio*path.get_min_speed()                 	    # Minimum speed in m/s

        tm = (Vm-u)/a					                                # Calculate the time for when max speed is met. 
        sm = u*tm + 0.5*a*tm*tm			                                # Calculate the distace travelled when max speed is met
        if sm > s/2.0:                                                  # If the distance is too short, we do not reach full speed 
            sm = s/2.0            
        if ds > sm:
            sm = 2.0*ds
        
        distances   = np.arange(0, sm, ds)		                        # Table of distances
        timestamps  = [(-u+np.sqrt(2.0*a*s+u*u))/a for s in distances]  # Make a table of times, the time at which a tick occurs
        delays      = np.diff(timestamps)/2.0			                # We are more interested in the delays pr second. 
        delays      = np.array([delays, delays]).transpose().flatten()	# Double the array so we have timings for up and down
        
        return list(delays)


