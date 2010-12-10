#!/usr/bin/env python

import roslib; roslib.load_manifest('sr_control_gui')
import rospy

from PyQt4 import QtCore, QtGui, Qt

from generic_plugin import GenericPlugin
from config import Config

from tabletop_object_detector.srv import TabletopDetection
from tabletop_object_detector.msg import TabletopDetectionResult
from household_objects_database_msgs.srv import GetModelDescription
from tabletop_collision_map_processing.srv import TabletopCollisionMapProcessing

class ObjectChooser(QtGui.QWidget):
    """
    Display the list of found objects
    """
    def __init__(self, parent, plugin_parent, title):
        QtGui.QWidget.__init__(self)
        self.plugin_parent = plugin_parent
        self.grasp = None
        self.title = QtGui.QLabel()
        self.title.setText(title)


    def draw(self):
        self.frame = QtGui.QFrame(self)

        self.tree = QtGui.QTreeWidget()
        self.connect(self.tree, QtCore.SIGNAL('itemDoubleClicked (QTreeWidgetItem *, int)'),
                     self.double_click)
        self.tree.setHeaderLabels(["Object Name", "Maker", "tags"])
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)
        self.tree.resizeColumnToContents(2)
        
        self.layout = QtGui.QVBoxLayout()
        self.layout.addWidget(self.title)
        self.layout.addWidget(self.tree)
        
        ###
        # SIGNALS
        ##
        self.plugin_parent.parent.parent.reload_object_signal_widget.reloadObjectSig['int'].connect(self.refresh_list)
        
        self.frame.setLayout(self.layout)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.frame)
        self.frame.show()
        self.setLayout(layout)
        self.show()
        
    def double_click(self, item, value):
        self.object = self.plugin_parent.found_objects[str(item.text(0))]
        print str(item.text(0)), " double clicked"
                
    def refresh_list(self, value=0):
        self.tree.clear()
        first_item = None
        object_names = self.plugin_parent.found_objects.keys()
        object_names.sort()
        for object_name in object_names:
            item = QtGui.QTreeWidgetItem(self.tree)
            if first_item == None:
                first_item = item
            
            item.setText(0, object_name)
            obj = self.plugin_parent.found_objects[object_name]
            item.setText(1, obj.maker)
            
            tags = ""
            for tag in obj.tags:
                tags += str(tag) + " ; "
            item.setText(2, tags)
            
            self.tree.resizeColumnToContents(0)
            self.tree.resizeColumnToContents(1)
            self.tree.resizeColumnToContents(2)
            
            #print "add"
            #self.tree.addTopLevelItem(item)
        return first_item
    
    
class ObjectSelection(GenericPlugin):  
    """
    Contact the tabletop object detector to get a list of the objects on top 
    of the table. Then possibility to select a detected object for picking it up.
    """
    name = "Object Selection"
        
    def __init__(self):
        GenericPlugin.__init__(self)

        self.service_object_detector = None
        self.service_db_get_model_description = None
        self.service_tabletop_collision_map = None
        
        self.found_objects = {}
        self.number_of_unrecognized_objects = 0

        self.frame = QtGui.QFrame()
        self.layout = QtGui.QVBoxLayout()
        self.btn_refresh = QtGui.QPushButton()
        self.btn_refresh.setText("Detect Objects")
        self.btn_refresh.setFixedWidth(130)
        self.frame.connect(self.btn_refresh, QtCore.SIGNAL('clicked()'), self.detect_objects)
        self.layout.addWidget(self.btn_refresh)
        
        self.object_chooser = ObjectChooser(self.window, self, "Objects Detected")
        self.layout.addWidget(self.object_chooser)
        
        self.frame.setLayout(self.layout)
        self.window.setWidget(self.frame)

        self.is_activated = False
    
    def activate(self):
        if self.is_activated:
            return
        self.is_activated = True

        if self.service_object_detector == None:
            rospy.wait_for_service('object_detection')
            self.service_object_detector = rospy.ServiceProxy('object_detection', TabletopDetection)

        if self.service_db_get_model_description == None:
            rospy.wait_for_service('objects_database_node/get_model_description')
            self.service_db_get_model_description = rospy.ServiceProxy('objects_database_node/get_model_description', GetModelDescription)

        if self.service_tabletop_collision_map == None:
            rospy.wait_for_service('/tabletop_collision_map_processing/tabletop_collision_map_processing')
            self.service_tabletop_collision_map = rospy.ServiceProxy('/tabletop_collision_map_processing/tabletop_collision_map_processing', TabletopCollisionMapProcessing)

        self.object_chooser.draw()

        GenericPlugin.activate(self)

    def detect_objects(self):
        self.found_objects.clear()
        try:
            objects = self.service_object_detector(True, True)
        except rospy.ServiceException, e:
            print "Service did not process request: %s" % str(e)
        
        self.number_of_unrecognized_objects = 0
        for index, cmi in zip(range(0, len(objects.detection.cluster_model_indices)), objects.detection.cluster_model_indices):
            # object not recognized
            if cmi == -1:
                self.number_of_unrecognized_objects += 1
                tmp_name = "unrecognized_" + str(self.number_of_unrecognized_objects)
                #TODO: change this
                self.found_objects[tmp_name] = objects.detection[0]
        
        # for the recognized objects
        for model in objects.detection.models:
            model_id = model.model_id
            
            try:
                model_desc = self.service_db_get_model_description(model_id)
            except rospy.ServiceException, e:
                print "Service did not process request: %s" % str(e)
            
            self.found_objects[model_desc.name] = model_desc
        
        self.parent.parent.reload_object_signal_widget.reloadObjectSig['int'].emit(1)
        
        self.process_collision_map(objects.detection)
    
    def process_collision_map(self, detection):
        res = 0
        try:
            res = self.service_tabletop_collision_map.call(detection, True, True, True, True, "world")
        except rospy.ServiceException, e:
            print "Service did not process request: %s" % str(e)
        
        print res
    
    def on_close(self):
        GenericPlugin.on_close(self)

    def depends(self):
        return Config.sr_object_selection_config.dependencies
                
