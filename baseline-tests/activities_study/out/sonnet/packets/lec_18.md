# Lecture 18: Understanding Tracking II

Transcript: transcripts/lec_18.txt

Goal: Explain the main tracking technologies used in VR and AR, how they estimate position and orientation, and how hybrid systems combine them.

Objectives:
- Explain the main categories of XR tracking and how electromechanical, electromagnetic, and acoustic/ultrasonic trackers estimate position and orientation.
- Explain how vision-based and structure-based tracking methods use optical or depth sensing to estimate pose.
- Describe how sensor-based and hybrid tracking methods use inertial, positional, motion-capture, and eye-tracking data, including their limitations.

Earlier lectures: 1: General Intro to XR; 2: Application Domains and System Categories; 3: Application Domains and System Categories; 4: Definitions; 5: Definitions; 6: Historical Evolution; 7: Historial Evolution; 8: Issues & Challenges; 9: Issues & Challenges; 10: Cybersickness; 11: Cybersickness; 12: Cybersickness; 13: VR Hardware; 14: VR Hardware; 15: AR Hardware; 16: Understanding Tracking I; 17: Understanding Tracking - I

## Unit U08: quiz

### Set X

X1. In the context of VR and AR, what are the primary things that can be tracked?
   A. Only the position of virtual objects.
   B. Only the movements of the user's body.
   C. Sense organs, body parts of the user, or objects in the surrounding.
   D. Only the orientation of the HMD.
   Marked correct: C
   Explanation: The transcript states that tracking involves tracking 'either sense organs or other body parts of the user or objects in the surrounding.'

X2. Which of the following is NOT listed as a broad category of tracking technology in the lecture?
   A. Electromechanical
   B. Electromagnetic
   C. Acoustic
   D. Quantum-based
   Marked correct: D
   Explanation: The lecture lists electromechanical, electromagnetic, acoustic, vision-based, inertial, and hybrid tracking technologies. Quantum-based is not mentioned.

X3. What is a characteristic of world-fixed electromechanical trackers?
   A. They are very light and wearable.
   B. They are typically cumbersome and may include a counterbalance.
   C. They are only used for eye-tracking.
   D. They use only magnetic fields.
   Marked correct: B
   Explanation: The lecture describes world-fixed electromechanical trackers as 'quite a cumbersome setup' and mentions 'mechanical pivoting with tracking sensors' and a 'counterbalance to make it stable.'

X4. What is a primary use case for wearable electromechanical trackers?
   A. Tracking individual GPS coordinates.
   B. Creating animated avatars of real human beings.
   C. Measuring the heartbeat of the user.
   D. Replacing the need for a display.
   Marked correct: B
   Explanation: The transcript mentions that 'real human beings wear these trackers and make movements, and those movements are tracked and translated to avatar movement in the virtual world.'

X5. What are the three main categories of optical sensors used in vision-based tracking?
   A. Infrared, visible light, and 3D structure.
   B. Ultrasonic, Laser, and Magnetic.
   C. Acoustic, Inertial, and Visual.
   D. Fiducial, Natural, and Model-based.
   Marked correct: A
   Explanation: The lecture states: 'There can be three main categories of optical sensors... One is infrared sensors, the second is visible light sensors, and the third is 3D structure sensors.'

X6. In infrared tracking, what does 'outside looking in' mean?
   A. Targets are attached to the user and cameras are in the environment.
   B. Cameras are mounted on the user and targets are in the environment.
   C. The user looks at an external screen.
   D. The sensor is inside the eye.
   Marked correct: A
   Explanation: In the 'outside looking in' case, 'targets are attached to objects that are being tracked with cameras external to the object... cameras... are placed in the environment.'

X7. Which of the following is a popular algorithm for natural feature detection and description?
   A. GPS
   B. SIFT
   C. MEMS
   D. RTK
   Marked correct: B
   Explanation: The transcript lists: 'SIFT, SURF, BRIEF, BRISK' as popular algorithms for natural feature detection.

X8. Which technique was specifically designed for augmented reality to improve accuracy and performance in smaller environments?
   A. SLAM
   B. PTAM
   C. RTK
   D. EOG
   Marked correct: B
   Explanation: The transcript says: 'Further optimizations of this SLAM technique led to PTAM, or Parallel Tracking and Mapping, which has been specifically designed for augmented reality.'

X9. What is a major limitation of GPS tracking mentioned in the lecture?
   A. It cannot be used for position.
   B. It provides low accuracy, particularly in indoor environments.
   C. It requires a line of sight to every satellite simultaneously.
   D. It only works with electromagnetic fields.
   Marked correct: B
   Explanation: The lecture states: 'The problem with GPS is that they generally offer low accuracy, particularly in the Indoor environment and only allows positional tracking.'

X10. Which techniques are mentioned as part of eye-tracking systems?
   A. SLAM and PTAM
   B. EOG and VOG
   C. SIFT and SURF
   D. RTK and GPS
   Marked correct: B
   Explanation: The transcript mentions 'electro-oculography or EOG, video-oculography or VOG techniques' as part of eye-tracking.

X11. Why are hybrid trackers generally preferred?
   A. They are cheaper to produce.
   B. They perform better than single-technology-based tracking.
   C. They are easier to understand for beginners.
   D. They require less power.
   Marked correct: B
   Explanation: The transcript notes: 'Typically, it has been found that hybrid trackers perform better than single-technology-based tracking.'

X12. Visible light sensors are common in which of the following devices?
   A. Only industrial robots.
   B. Smartphones, laptops, and tablet PCs.
   C. Only VR headsets.
   D. Satellite systems.
   Marked correct: B
   Explanation: The transcript mentions these cameras can be found in 'almost all consumer-grade electronic devices, including laptops, smartphones, and tablet PCs.'

### Set Y

Y1. Which description matches a world-fixed electromechanical tracker?
   A. a body-worn frame used to move an animated avatar
   B. a microphone paired with a stationary ultrasonic speaker
   C. a display attached to a mechanically pivoted tracked setup
   D. a receiver attached to a headset and moved through magnetic fields
   Marked correct: C
   Explanation: A world-fixed electromechanical tracker pairs a display with a tracked setup that has mechanical pivoting. The body-worn frame describes a wearable tracker, while magnetic receivers and ultrasonic microphones belong to other tracking methods.

Y2. What practical drawback is associated with wearable electromechanical trackers?
   A. They are limited by ambient light for optical targets
   B. They are limited by line of sight to ultrasonic transmitters
   C. They are not very comfortable and are quite cumbersome
   D. They are fixed to a display with a counterbalance
   Marked correct: C
   Explanation: Wearable electromechanical trackers are not very comfortable and are quite cumbersome, and they are used in limited, highly specialized setups. A counterbalanced display belongs to a world-fixed setup, while line-of-sight and ambient-light concerns belong to ultrasonic and optical tracking.

Y3. How does an electromagnetic tracker obtain the real-time position of a headset?
   A. By comparing images from cameras that watch a marker
   B. By timing ultrasonic pulses between the speakers and microphones
   C. By measuring joint angles in a mechanical linkage
   D. By reading currents induced in the receiver by magnetic fields
   Marked correct: D
   Explanation: An electromagnetic tracker uses magnetic fields from a stationary transmitter to induce currents in a receiver on the headset, and those signals are used to determine position. The other options describe ultrasonic, vision-based, or electromechanical tracking instead.

Y4. What does a vision-based tracker determine for a tracked object?
   A. Joint rotation angles
   B. Magnetic field direction
   C. Ultrasonic travel time
   D. Position and orientation
   Marked correct: D
   Explanation: Vision-based trackers determine poses, such as position and orientation, using optical sensors or cameras. Magnetic field direction, ultrasonic travel time, and joint angles belong to other tracking approaches.

Y5. What is true of outside-in infrared tracking?
   A. Its cameras are in the environment and detect the tracked object without attached targets
   B. Its cameras are in the environment and detect targets on the tracked object
   C. Its cameras are on the user and detect targets in the environment
   D. Its cameras are on the tracked object and detect targets in the environment
   Marked correct: B
   Explanation: In outside-in infrared tracking, environment-placed cameras detect targets attached to the tracked object to determine pose and position. Inside-out tracking instead uses a camera mounted with the user to detect external targets.

Y6. What makes optical cameras a practical sensor choice for visible light tracking?
   A. Their use of infrared targets attached to the tracked object
   B. Their availability mainly in dedicated augmented reality headsets
   C. Their abundance in consumer-grade electronic devices
   D. Their need for small colored LEDs attached to the tracked object
   Marked correct: C
   Explanation: Visible light tracking often uses optical cameras because such cameras are already common in many consumer devices. Infrared targets and colored LEDs are not required by optical cameras themselves.

Y7. Which fiducial type supports detection at greater distances?
   A. A multi-ring fiducial
   B. A constant width ring fiducial
   C. A proportional width ring fiducial
   D. A small colored LED fiducial
   Marked correct: A
   Explanation: Multi-ring fiducials are used for detection at greater distances. Proportional and constant width ring fiducials differ in how their appearance or ring width behaves with distance, and small colored LEDs are another kind of fiducial.

Y8. How does PTAM differ from SLAM in its handling of tracking and mapping?
   A. It handles camera tracking and environment mapping as one fixed combined activity
   B. It handles camera tracking and stored-model matching as separate activities
   C. It handles fiducial matching and environment mapping as separate activities
   D. It handles camera tracking and environment mapping as separate activities
   Marked correct: D
   Explanation: PTAM is an optimization of SLAM that separates camera tracking from environment mapping into distinct activities. It does not merge those activities, nor replace them with fiducial or stored-model matching.

Y9. Which output is characteristic of 3D structure tracking?
   A. Images built from point positions
   B. Poses built from point positions
   C. Markers built from point positions
   D. Models built from point positions
   Marked correct: D
   Explanation: 3D structure tracking creates 3D models of structures in the environment from sensed point positions; it does not directly create images, markers, or pose estimates.

Y10. What do inertial trackers report?
   A. Absolute-distance readings from a fixed base station
   B. Absolute-value readings for orientation, velocity, or acceleration
   C. Absolute-position readings for the surrounding room
   D. Rate-of-change readings for orientation, velocity, or acceleration
   Marked correct: D
   Explanation: Inertial trackers measure changes such as orientation, translation velocity, or acceleration, rather than absolute values. They do not by themselves provide absolute position or distance from a fixed reference.

Y11. Why are inertial trackers readily usable on smartphones and head-mounted displays?
   A. They are built into the device but have a short range limitation
   B. They rely on external beacons and have a room-scale limitation
   C. They are built into the device and have no range limitation
   D. They rely on GPS satellites and have an outdoor coverage limitation
   Marked correct: C
   Explanation: Inertial trackers are typically MEMS-based sensors inside the user's device, so they can be used readily without an external tracking range. They do not depend on beacons or GPS for basic tracking.

Y12. What do eye-tracking systems typically track?
   A. The user's full body movement
   B. The 3D positions of points in a scene
   C. The change in orientation of a device
   D. The user's gaze point or area of the gaze
   Marked correct: D
   Explanation: Eye-tracking systems usually follow where the user is looking. Full body movement, scene structure, and device orientation are tracked by other methods.

### Set Z

Z1. What can be tracked in the context of XR systems?
   A. Sense organs, body parts, or surrounding objects
   B. Virtual objects and user avatars in the surrounding scene
   C. User's gaze point and hand positions
   D. Physical buttons and digital screen inputs
   Marked correct: A
   Explanation: Tracking involves monitoring sense organs, other body parts of the user, or objects in the surrounding environment.

Z2. What are the two main types of electromechanical trackers?
   A. World-fixed or wearable
   B. Internal or external
   C. Active or passive
   D. Static or dynamic systems
   Marked correct: A
   Explanation: Electromechanical trackers can be world-fixed or wearable, which are worn on the body of the user.

Z3. What is a characteristic of world-fixed electromechanical trackers?
   A. Optical cameras in the surrounding environment
   B. Magnetic transmitters in the surrounding environment
   C. Mechanical pivoting with attached tracking sensors
   D. Wearable sensors on the user's body
   Marked correct: C
   Explanation: World-fixed electromechanical trackers feature mechanical pivoting with tracking sensors attached to a setup, often including a counterbalance.

Z4. What is a key difference between acoustic and electromagnetic tracking?
   A. The requirement for a clear line of sight
   B. The use of stationary transmitters
   C. The movement of the receiver element
   D. The generation of electric currents
   Marked correct: A
   Explanation: Acoustic tracking requires a line of sight between the transmitter and receiver, which is not a requirement for electromagnetic tracking.

Z5. What components act as transmitters and receivers in acoustic tracking?
   A. LEDs and photodiodes
   B. Speakers and microphones
   C. Cameras and sensors
   D. Antennas and coils
   Marked correct: B
   Explanation: In acoustic tracking, transmitters are often called speakers and receivers are called microphones.

Z6. How is pose determined in vision-based trackers?
   A. Using electromechanical kinematic links
   B. Using magnetic fields from transmitters
   C. Using ultrasonic signals from speakers
   D. Using optical sensors or cameras
   Marked correct: D
   Explanation: In vision-based trackers, poses such as position and orientation are determined using optical sensors or cameras.

Z7. Why is infrared tracking robust against poor ambient lighting?
   A. It relies on infrared sensing rather than visible light
   B. It requires high brightness from surroundings
   C. It utilizes high-frequency DC currents
   D. It uses high-power ultrasonic signals
   Marked correct: A
   Explanation: Because infrared tracking relies on infrared sensing rather than visible light, adverse illumination effects like poor lighting or shadows do not affect performance.

Z8. Where are visible light sensors commonly found today?
   A. Fixed infrastructure and automated vehicles
   B. Commercial drones and industrial robots
   C. In laptops, smartphones, and tablet PCs
   D. Static environment mapping and navigation
   Marked correct: C
   Explanation: Visible light cameras are common in almost all consumer-grade electronic devices, including laptops, smartphones, and tablet PCs.

Z9. How does natural feature tracking identify environment features?
   A. Detecting features that are common to all objects
   B. Detecting features unique to the surroundings
   C. Detecting features that are manually added
   D. Detecting features unique to the moving object
   Marked correct: B
   Explanation: Natural feature tracking uses computer vision algorithms to detect features that are unique to the surroundings with respect to the object.

Z10. What was the original application of SLAM?
   A. Augmented reality
   B. Satellite positioning
   C. Human motion capture
   D. Robot navigation
   Marked correct: D
   Explanation: The SLAM technique was originally developed for robot navigation.

Z11. What specific depth sensor technology is used in Kinect Fusion?
   A. An ultrasonic depth sensor
   B. An infrared depth sensor
   C. A structured light depth sensor
   D. A visible light depth sensor
   Marked correct: C
   Explanation: Kinect Fusion uses data obtained from Kinect's structured light depth sensor to create 3D models.

Z12. What do inertial trackers measure instead of absolute values?
   A. The absolute position in a 3D space
   B. The total distance traveled by the user
   C. The static orientation of the object
   D. The rate of change in orientation or velocity
   Marked correct: D
   Explanation: Inertial trackers measure the rate of change in object orientation, translation velocity, or acceleration, but they cannot measure absolute values.

### Set W

W1. Which of the following is classified as a primary category of tracking technology in XR systems?
   A. line-of-sight tracking
   B. optical sensor tracking
   C. world-fixed tracking
   D. inertial tracking
   Marked correct: D
   Explanation: Inertial tracking is one of the primary categories of tracking technologies, whereas the other options describe specific types (world-fixed), requirements (line-of-sight), or mechanisms (optical sensor) that belong within the primary categories.

W2. Which tracking technology can function even if there is an obstacle between the transmitter and the receiver?
   A. Acoustic tracking
   B. Vision-based tracking
   C. Electromagnetic tracking
   D. Electromechanical tracking
   Marked correct: C
   Explanation: Electromagnetic tracking does not require a line of sight between the transmitter and the receiver, whereas acoustic tracking does.

W3. Which components are used as the transmitter and receiver in an acoustic tracking system?
   A. Speakers and microphones
   B. Kinematic links and mechanical joints
   C. Cameras and infrared sensors
   D. Antennas and electromagnetic coils
   Marked correct: A
   Explanation: In acoustic (ultrasonic) tracking, the stationary transmitters are called speakers and the moving receivers are called microphones.

W4. Why is infrared tracking robust to adverse illumination effects such as poor ambient lighting or harsh shadows?
   A. The sensors have a higher dynamic range for visible light
   B. The system averages light from multiple environment cameras
   C. The targets emit a light that is brighter than the surroundings
   D. It relies on infrared sensing rather than visible light sensing
   Marked correct: D
   Explanation: Infrared tracking specifically uses infrared sensing, which is unaffected by the visible light conditions like shadows or poor lighting.

W5. What characteristic of infrared tracking targets makes them easy to detect?
   A. they emit or reflect light with high brightness
   B. they are placed in a fixed position in the environment
   C. they communicate wirelessly with the optical sensors
   D. they are made of durable materials for virtual reality
   Marked correct: A
   Explanation: Detection is easy because the targets emit or reflect light which provides high brightness compared to the surrounding environment.

W6. What is the primary purpose of adding fiducials to an environment?
   A. detect natural features in the surroundings
   B. identify unique descriptors for features
   C. provide high brightness in poor lighting
   D. aid registration and tracking of the object
   Marked correct: D
   Explanation: Fiducials are artificial landmarks added to the environment to assist in the registration and tracking of the object being monitored.

W7. What determines the complexity of fiducial tracking?
   A. the brightness of the environment
   B. the distance from the camera
   C. the number of sensors used
   D. the kind of fiducial used
   Marked correct: D
   Explanation: The complexity of fiducial tracking varies based on the specific type of artificial landmark used, such as LEDs, pieces of paper, or different types of ring fiducials.

W8. How does natural feature tracking register a camera's pose in real time?
   A. Tracking the physical movement of the lens
   B. Using features in the natural environment
   C. Using artificial landmarks in the environment
   D. Following a pre-defined path in the software
   Marked correct: B
   Explanation: Natural feature tracking utilizes features that exist in the natural environment, whereas fiducial tracking uses artificial landmarks.

W9. What is the primary role of unique descriptors for each detected feature in natural feature tracking?
   A. To identify and differentiate one feature from others
   B. To calculate the motion speed of the features
   C. To measure the brightness of the environment
   D. To determine the distance of the camera from the object
   Marked correct: A
   Explanation: Descriptors are calculated to identify and differentiate one feature from another.

W10. What types of features are detected as unique to the surroundings in natural feature tracking?
   A. Textured surfaces and color blocks in the scene
   B. Artificial landmarks and QR codes in the scene
   C. Points, corners, and line intersections
   D. Outer edges of the virtual objects and models
   Marked correct: C
   Explanation: Natural feature tracking specifically looks for features like points, corners, and line intersections in the environment.

W11. What started the trend of making 3D structure sensing sensors more affordable in recent years?
   A. The use of MEMS technology
   B. The Microsoft Kinect device
   C. The development of PTAM
   D. The development of SLAM
   Marked correct: B
   Explanation: The trend toward affordable 3D structure sensing sensors began with the introduction of the Microsoft Kinect device.

W12. What are the physical configurations for eye-tracking systems?
   A. head-mounted, remote, or part of trackers
   B. optical, infrared, or electro-oculography
   C. high-resolution camera-based tracking
   D. tracking the gaze point or area of the user
   Marked correct: A
   Explanation: Eye-tracking systems can be head-mounted, remote, or integrated as part of other trackers. The other options describe the internal techniques, the specific sensors used, or what the system actually tracks.

## Unit U09: recap

### Set X

X1. Summary text: Electromechanical trackers are mechanical structures of links and sensor joints, and they come in world-fixed and wearable forms. The world-fixed form is a cumbersome display-attached mechanism. The wearable form translates a person's movements into animated avatar movement, while also being uncomfortable, cumbersome, and used in limited, highly specialized setups.

X2. Point: Acoustic or ultrasonic tracking determines real-time head position using ultrasonic signals from transmitters to HMD microphones.

X3. Point: Electromagnetic and acoustic or ultrasonic trackers both use stationary transmitters and receivers that move with the head or body.

X4. Point: Acoustic or ultrasonic tracking requires line of sight, whereas electromagnetic tracking does not require this line of sight.

X5. Summary text: Electromagnetic and acoustic or ultrasonic trackers estimate a head’s real-time position using signals between transmitters and receivers. Electromagnetic tracking uses magnetic fields, while acoustic or ultrasonic tracking uses ultrasonic signals. Although both use stationary transmitters and receivers that move with the head or body, acoustic tracking needs line of sight and electromagnetic tracking does not.

X6. Point: Infrared tracking is among the earliest vision-based tracking techniques developed and used in VR or AR.

X7. Point: Visible light tracking has three techniques: fiducial, natural feature, and model-based tracking.

X8. Point: Fiducial tracking adds artificial landmarks to the environment to aid registration and tracking of an object.

X9. Point: Natural feature tracking’s computer vision algorithms detect unique features in the surroundings of the tracked object.

X10. Point: Kinect Fusion creates 3D models from Kinect structured-light depth data and uses those models to track the Kinect's pose.

X11. Summary text: 3D structure tracking creates 3D models of real structures from 3D point positions obtained with commercial sensors, and those models support augmenting the real-world view. The sensors used for this technique became affordable, beginning with Microsoft Kinect. Kinect Fusion illustrates the approach by turning Kinect structured-light depth data into 3D models that also track the Kinect's pose.

X12. Point: Hybrid trackers combine two or more basic tracking methods and typically outperform single-technology trackers.

### Set Y

Y1. Point: Earlier sessions covered the definition of tracking and established how it identifies users and objects.

Y2. Point: Specific examples of wearable trackers include the IGS 190 and the Gypsy Gyro.

Y3. Point: This system employs stationary transmitters (speakers) and moving receivers (microphones).

Y4. Point: Pose estimation in vision-based systems is determined using optical sensors or cameras.

Y5. Point: There are three primary types of optical sensors: infrared, visible light, and 3D structure sensors.

Y6. Point: Infrared tracking was among the earliest vision-based techniques developed for the VR and AR fields.

Y7. Point: Fiducial tracking uses artificial landmarks like colored LEDs or paper to aid in registration.

Y8. Point: This method relies on advanced image processing algorithms to create unique descriptors for features.

Y9. Point: Popular algorithms for natural feature tracking include SIFT, SURF, BRIEF, and BRISK.

Y10. Point: 3D structure tracking uses depth sensors to detect 3D positions of points in a scene.

Y11. Point: GPS is a positional tracking device primarily useful for outdoor environments.

Y12. Point: RTK, or real-time kinematic technology, can be used to improve the accuracy of GPS signals indoors or outdoors. 

### Set Z

Z1. Point: Tracking targets include sense organs, body parts, or objects in the surroundings.

Z2. Point: Tracking technologies are categorized as electromechanical, electromagnetic, acoustic, vision-based, inertial, or hybrid.

Z3. Point: World-fixed electromechanical trackers are typically a cumbersome setup.

Z4. Point: Electromagnetic trackers use a magnetic field from a stationary transmitter to determine the position of a moving receiver.

Z5. Point: A transmitter in an electromagnetic tracker can produce three orthogonal magnetic fields.

Z6. Point: Acoustic tracking uses transmitters like speakers and receivers like microphones.

Z7. Point: Infrared tracking uses targets that emit or reflect light, making it robust to adverse illumination.

Z8. Point: SIFT, SURF, BRIEF, and BRISK are popular algorithms for natural feature tracking.

Z9. Point: SLAM creates and updates a map of the environment while localizing positions in real time.

Z10. Point: PTAM is an optimization of SLAM for augmented reality that improves accuracy for small environments but has high computational requirements for larger environments.

Z11. Point: 3D structure sensing uses depth sensors to create 3D models of objects for pose tracking and augmentation.

Z12. Point: Inertial trackers are self-contained sensors that measure rates of change in orientation, velocity, or acceleration.

### Set W

W1. Point: The others category of tracking technologies includes location-based and hybrid tracking technologies.

W2. Point: A world-fixed electromechanical tracker is a cumbersome setup with a display, mechanical pivoting, tracking sensors, and a counterbalance to make it stable.

W3. Point: Acoustic tracking uses ultrasonic signals from stationary speakers to determine the real-time position and orientation of moving microphones.

W4. Point: Both systems use stationary transmitters and moving receivers, but acoustic tracking requires a line of sight while electromagnetic does not.

W5. Summary text: Visible light tracking utilizes optical cameras and is classified into fiducial tracking, natural feature tracking, and model-based tracking. Fiducial tracking specifically utilizes artificial landmarks, and the complexity of the method depends on the specific design of those landmarks.

W6. Point: Camera pose is estimated by matching descriptors from the scene with descriptors from the object.

W7. Point: SIFT, SURF, BRIEF, and BRISK are popular algorithms for natural feature detection and description.

W8. Point: SLAM was originally developed for robot navigation and subsequently adapted for augmented reality.

W9. Point: Parallel Tracking and Mapping (PTAM) optimizes SLAM by performing tracking and mapping as separate activities.

W10. Point: 3D structure tracking uses commercial sensors to obtain 3D positions of points and create models for real-world augmentation.

W11. Point: Commercial sensors capable of detecting 3D structure information became affordable in recent years.

W12. Summary text: 3D structure tracking uses commercial sensors to obtain 3D point positions and create models for augmenting real-world views. These sensors became affordable in recent years, leading to the development of systems like Kinect Fusion. Kinect Fusion uses structured light depth sensors to create 3D models of real objects and environments, which are then used to track the pose of the Kinect.

## Unit U10: open question

### Set X

X1. Question: How does acoustic tracking differ from electromagnetic tracking in terms of environmental requirements?
   Reference answer: Acoustic tracking requires line of sight between the stationary transmitter and the moving receiver, meaning there should not be any obstacle in between. Electromagnetic tracking does not have this requirement, as it uses a magnetic field produced by a stationary transmitter to determine the position of a moving receiver.

X2. Question: Why is infrared tracking robust to adverse illumination effects such as poor ambient lighting or harsh shadows?
   Reference answer: Infrared tracking is robust to adverse illumination effects because it relies on infrared sensing rather than visible light sensing. It uses targets that emit or reflect light, which makes detection easy due to high brightness compared to the surroundings.

X3. Question: How does Parallel Tracking and Mapping (PTAM) differ from Simultaneous Localization and Mapping (SLAM) in how they handle tracking and mapping?
   Reference answer: PTAM allows tracking of the camera and mapping of the environment as separate activities. In contrast, SLAM is a technique that simultaneously creates and updates a map of the real environment while localizing positions within it.

### Set Y

Y1. Question: How does the environmental requirement for line of sight differ between acoustic tracking and electromagnetic tracking?
   Reference answer: Acoustic tracking requires a line of sight between the stationary transmitter and the receiver. In contrast, electromagnetic tracking does not require this line of sight.

Y2. Question: How does Parallel Tracking and Mapping (PTAM) improve upon Simultaneous Localization and Mapping (SLAM) for augmented reality applications?
   Reference answer: Parallel Tracking and Mapping (PTAM) improves both the accuracy of tracking and the overall performance. It achieves this by allowing tracking of the camera and mapping of the environment to occur as separate activities.

Y3. Question: What distinguishes the camera placement in outside-in infrared tracking from inside-out infrared tracking?
   Reference answer: In outside-in infrared tracking, cameras are placed in the environment to detect targets attached to the object. In inside-out infrared tracking, the camera is mounted with the user and detects external targets.

### Set Z

Z1. Question: Compare and contrast acoustic (ultrasonic) tracking and electromagnetic tracking in terms of their physical requirements and operational limitations.
   Reference answer: Both technologies utilize a setup where transmitters are stationary in the environment and receivers move with the user (e.g., attached to a headset). The primary difference lies in their signal propagation: acoustic tracking requires a clear line of sight between the transmitter and receiver, meaning obstacles can block the signal. In contrast, electromagnetic tracking does not require a line of sight because it relies on magnetic fields generated by the transmitter.

Z2. Question: In the context of vision-based tracking, why is infrared sensing often preferred over visible light sensing in certain environments, and what are the trade-offs regarding hardware availability?
   Reference answer: Infrared tracking is preferred in environments with adverse illumination (such as poor lighting or harsh shadows) because it is robust to these effects, as it relies on targets that emit or reflect infrared light. The trade-off is that while infrared is robust, visible light sensors are far more abundant and prevalent in consumer-grade electronics like smartphones, laptops, and wearable devices.

Z3. Question: Explain the evolution from SLAM to PTAM in vision-based tracking and identify the specific environmental limitation of PTAM.
   Reference answer: SLAM (Simultaneous Localization and Mapping) allows for drift-free tracking in unknown environments by creating and updating a map in real-time, a technique originally developed for robot navigation. PTAM (Parallel Tracking and Mapping) is an optimization of SLAM designed specifically for AR, where tracking and mapping are handled as separate activities to improve accuracy and performance. However, PTAM is primarily suited for smaller environments because the computational requirements for larger environments are very high.

### Set W

W1. Question: Why can an electromagnetic tracker estimate a receiver's position when obstacles block the transmitter-receiver path, while an acoustic tracker cannot?
   Reference answer: Electromagnetic tracking does not require line of sight between transmitter and receiver, whereas acoustic tracking does. Both rely on stationary transmitters and receivers that move with the head or body. Electromagnetic trackers obtain the receiver's real-time position from the direction of the magnetic field, while acoustic tracking uses ultrasonic signals to determine the receiver's position, so an obstacle blocks the acoustic measurement.

W2. Question: Why is parallel tracking and mapping considered an optimization of simultaneous localization and mapping that is more suitable for smaller than larger environments?
   Reference answer: PTAM is an SLAM optimization because it separates camera tracking from environment mapping. SLAM creates and updates a map while localizing, but PTAM's separate activities improve tracking accuracy and performance. It is more suitable for smaller environments because its computational requirements for larger ones are quite high.

W3. Question: Why is the global positioning system more useful as part of a hybrid tracking system than as the only tracking method for an XR system?
   Reference answer: The global positioning system is more useful in a hybrid tracking system because GPS generally offers low accuracy and allows only positional tracking, while a hybrid tracker uses two or more basic tracking systems and typically performs better than single-technology-based tracking. GPS is typically used when accurate position registration is not important, when an approximation is good enough, or as part of a hybrid system.

## Unit U11: odd one out

### Set X

X1. Items: Fiducial tracking | Natural feature tracking | Model-based tracking | Infrared tracking
   Marked odd: Infrared tracking
   Reason: Fiducial, natural feature, and model-based tracking are techniques of visible light tracking; infrared tracking is a type of vision-based tracking.

X2. Items: Accelerometer | Camera | Magnetometer | Gyroscope
   Marked odd: Camera
   Reason: Gyroscope, accelerometer, and magnetometer are primary inertial sensors; a camera is an optical sensor.

### Set Y

Y1. Items: Acoustic tracking | Model-based tracking | Fiducial tracking | Natural feature tracking
   Marked odd: Acoustic tracking
   Reason: Fiducial, natural feature, and model-based tracking are types of visible light tracking; acoustic tracking is a type of ultrasonic tracking.

Y2. Items: Gyroscope | Magnetometer | 3D structure sensor | Accelerometer
   Marked odd: 3D structure sensor
   Reason: Gyroscope, accelerometer, and magnetometer are the primary sensors for inertial tracking; a 3D structure sensor is used for 3D structure sensing.

Y3. Items: Hybrid trackers | Acoustic | Electromagnetic | Electromechanical
   Marked odd: Hybrid trackers
   Reason: Electromechanical, electromagnetic, and acoustic are basic tracking technologies; hybrid trackers are systems that combine multiple basic tracking methods.

### Set Z

Z1. Items: Model-Based Tracking | Fiducial Tracking | Infrared Tracking | Natural Feature Tracking
   Marked odd: Infrared Tracking
   Reason: Fiducial, natural-feature and model-based tracking are visible-light tracking techniques, whereas infrared tracking is a vision-based technique that uses infrared sensing rather than visible-light sensing.

Z2. Items: Accelerometer | Gyroscope | Microphone | Magnetometer
   Marked odd: Microphone
   Reason: A gyroscope, accelerometer and magnetometer are primary inertial sensors, whereas a microphone is an acoustic tracking receiver.

Z3. Items: Scale Invariant Feature Transform | Simultaneous Localization and Mapping | Binary Robust Independent Elementary Features | Speeded Up Robust Features
   Marked odd: Simultaneous Localization and Mapping
   Reason: SIFT, SURF and BRIEF are natural-feature detection and description algorithms, whereas SLAM is a tracking technique that creates and updates an environment map.

### Set W

W1. Items: Fiducial tracking | Natural feature tracking | Model-based tracking | Electromagnetic tracking
   Marked odd: Electromagnetic tracking
   Reason: Fiducial, natural feature, and model-based tracking are all sub-categories of visible light-based tracking, while electromagnetic tracking is a separate major category of tracking technology.

W2. Items: Gyroscope | Accelerometer | Magnetometer | Ultrasonic sensor
   Marked odd: Ultrasonic sensor
   Reason: Gyroscope, accelerometer, and magnetometer are the primary sensors used for inertial tracking, while ultrasonic sensors are used for acoustic tracking.

W3. Items: Infrared tracking | Visible light tracking | 3D structure tracking | Inertial tracking
   Marked odd: Inertial tracking
   Reason: Infrared, visible light, and 3D structure tracking are all categorized as vision-based (optical) sensors, whereas inertial tracking is a separate primary category.

## Unit U12: put in order

### Set X

X1. Title: Order the stages of natural feature tracking
   1. Unique features such as points, corners, and line intersections are detected
   2. Unique descriptors are calculated for each detected feature
   3. Camera pose is estimated by matching scene features with object features using descriptors

### Set Y

Y1. Title: Order the steps of natural feature tracking
   1. Use advanced image processing algorithms or computer vision techniques
   2. Detect unique features in the surroundings
   3. Create unique descriptors for each feature
   4. Identify and differentiate the features from other features
   5. Match features detected in the scene with those detected in the object
   6. Estimate the pose of the object to be tracked

### Set Z

(no items: this system made none)

### Set W

W1. Title: Natural Feature Tracking Process
   1. Detect unique features in the natural environment, such as points, corners, and line intersections.
   2. Create unique descriptors for each detected feature using computer vision algorithms.
   3. Match the features detected in the scene with the features detected on the object to be tracked.
   4. Estimate the pose (position and orientation) of the object based on these matches.

## Unit U13: concept map

### Set X

X1. Tracking Technologies --includes--> Electromechanical Trackers

X2. Tracking Technologies --includes--> Vision-based Trackers

X3. Tracking Technologies --includes--> Inertial Trackers

X4. Tracking Technologies --includes--> GPS

X5. Tracking Technologies --includes--> Hybrid Trackers

X6. Electromechanical Trackers --has type--> World-fixed Electromechanical Trackers

X7. Electromechanical Trackers --has type--> Wearable Electromechanical Trackers

X8. Optical Sensors --includes--> Infrared Tracking

X9. Optical Sensors --includes--> Visible Light Tracking

X10. Visible Light Tracking --includes--> Model-based Tracking

X11. Inertial Trackers --includes--> Gyroscope

X12. Inertial Trackers --includes--> Accelerometer

### Set Y

Y1. world-fixed tracker --has--> tracking sensor

Y2. acoustic tracking --uses--> ultrasonic signal

Y3. acoustic tracking --requires--> line of sight

Y4. electromagnetic tracking --does not require--> line of sight

Y5. vision-based tracker --uses--> camera

Y6. camera --in outside looking in infrared tracking detects--> target

Y7. natural feature tracking --requires advanced techniques of--> image processing

Y8. simultaneous localization and mapping --allows drift-free--> tracking

Y9. inertial measurement unit --can be readily used for--> tracking

Y10. hybrid software-level sensor --can be designed using--> gyroscope

Y11. motion capture --is packaged as--> motion capture suit

Y12. motion capture suit --includes--> tracking sensor

### Set Z

Z1. Tracking Technologies --is a kind of--> Electromagnetic Trackers

Z2. Tracking Technologies --is a kind of--> Hybrid/Other Trackers

Z3. Electromagnetic Trackers --uses--> Stationary Transmitter

Z4. Acoustic/Ultrasonic Trackers --requires--> Line of Sight

Z5. Vision-based Trackers --determines--> Pose

Z6. Optical Sensors --is a type of--> Visible Light Sensors

Z7. Optical Sensors --is a type of--> 3D Structure Sensors

Z8. Visible Light Sensors --is a method of--> Model-based Tracking (SLAM)

Z9. Model-based Tracking (SLAM) --optimized to--> PTAM

Z10. Inertial Trackers --comprises--> Accelerometer

Z11. Inertial Trackers --comprises--> Magnetometer

Z12. Hybrid/Other Trackers --includes--> GPS

## Unit U14: recall

### Set X

X1. Prompt: What is tracking?
   Answer: The process of determining the position and orientation (pose) of a user, their body parts, or objects within a virtual or augmented environment.
   Taught in: lecture 16 (Understanding Tracking I)

X2. Prompt: What is outside-in tracking?
   Answer: A tracking method where sensors (like cameras) are placed in the external environment to track targets attached to the user or objects.
   Taught in: lecture 17 (Understanding Tracking - I)

X3. Prompt: What is inside-out tracking?
   Answer: A tracking method where cameras are mounted directly on the wearable device to track the surrounding environment.
   Taught in: lecture 17 (Understanding Tracking - I)

X4. Prompt: What is VR hardware?
   Answer: Physical equipment, such as Head-Mounted Displays (HMDs) and controllers, used to interact with and experience virtual environments.
   Taught in: lecture 13 (VR Hardware)

X5. Prompt: What is AR hardware?
   Answer: Physical devices, such as smart glasses or mobile devices, that overlay digital information onto the real world.
   Taught in: lecture 15 (AR Hardware)

X6. Prompt: What is motion capture?
   Answer: A technique used to digitally record the movements of humans or objects, often utilizing wearable suits equipped with sensors.
   Taught in: lecture 14 (VR Hardware)

### Set Y

Y1. Prompt: What is Inside-Out tracking?
   Answer: A tracking technology where cameras are mounted on the user's device (e.g., a headset) to detect and track external targets in the environment.
   Taught in: lecture 16 (Understanding Tracking I)

Y2. Prompt: What is Outside-In tracking?
   Answer: A tracking technology where external cameras placed in the environment are used to track targets attached to the user or objects.
   Taught in: lecture 16 (Understanding Tracking I)

Y3. Prompt: What is VR Hardware?
   Answer: The physical components and devices, such as headsets and controllers, used to interact with and experience virtual reality environments.
   Taught in: lecture 13 (VR Hardware)

Y4. Prompt: What is AR Hardware?
   Answer: The physical devices used to project or overlay digital information onto the real-world environment.
   Taught in: lecture 15 (AR Hardware)

Y5. Prompt: What is Motion Capture?
   Answer: A technique used to digitally record and translate the movements of real-world entities, typically humans, using wearable suits and sensors.
   Taught in: lecture 13 (VR Hardware)

Y6. Prompt: What is the basic idea of tracking?
   Answer: The process of identifying what is being tracked (e.g., sense organs, body parts, or objects) and determining how those positions and orientations are measured.
   Taught in: lecture 16 (Understanding Tracking I)

### Set Z

Z1. Prompt: What is registration?
   Answer: Registration is the step in the tracking process that estimates the initial position and orientation of the sensor or user, so the starting point is known before movement is tracked, and sets the initial alignment between the real and virtual worlds. It may be aided by fiducial markers, reflectors, or tags, or performed without them using computer vision.
   Taught in: lecture 16 (Understanding Tracking I)

Z2. Prompt: What is inertial measurement unit (IMU)?
   Answer: An inertial measurement unit (IMU) is a self-contained composite hardware unit that mainly contains a gyroscope, accelerometer, and magnetometer to measure changes in orientation, translation velocity, or acceleration rather than absolute values.
   Taught in: lecture 17 (Understanding Tracking - I)

Z3. Prompt: What is gyroscope?
   Answer: A gyroscope is an inertial sensor that captures angular velocity. In an inertial measurement unit, it is a main component, and sensor tracking relies mainly on its readings.
   Taught in: lecture 17 (Understanding Tracking - I)

Z4. Prompt: What is accelerometer?
   Answer: An accelerometer is an inertial sensor that captures linear acceleration along the x, y, and z axes, and in an inertial measurement unit its readings can be used to detect drift errors.
   Taught in: lecture 17 (Understanding Tracking - I)

Z5. Prompt: What is magnetometer?
   Answer: A magnetometer is a sensor that captures magnetic field strength along the x, y, and z axes and can be used to detect drift errors in tracking.
   Taught in: lecture 17 (Understanding Tracking - I)

Z6. Prompt: What is augmented reality (AR)?
   Answer: Augmented reality (AR) is an enhanced version of reality created by technology, in which computer-generated digital content is overlaid on the real world in real time and registered in 3D, so the user perceives and interacts with the enhanced environment.
   Taught in: lecture 1 (General Intro to XR)
