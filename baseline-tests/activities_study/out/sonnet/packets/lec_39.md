# Lecture 39: System Design

Transcript: transcripts/lec_39.txt

Goal: Explain how object interaction in immersive experience design is organized into selection and manipulation, and describe the main techniques and criteria for choosing them.

Objectives:
- Explain the broad categories of interaction in immersive experience design.
- Describe object selection techniques and the parameters used to choose among them.
- Describe object manipulation techniques, including hand-based, indirect, bimanual, and integrated hybrid approaches.

Earlier lectures: 1: General Intro to XR; 2: Application Domains and System Categories; 3: Application Domains and System Categories; 4: Definitions; 5: Definitions; 6: Historical Evolution; 7: Historial Evolution; 8: Issues & Challenges; 9: Issues & Challenges; 10: Cybersickness; 11: Cybersickness; 12: Cybersickness; 13: VR Hardware; 14: VR Hardware; 15: AR Hardware; 16: Understanding Tracking I; 17: Understanding Tracking - I; 18: Understanding Tracking II; 19: VR Software; 20: VR Software; 21: AR Software; 22: AR Software; 23: XR as Interactive Systems; 24: XR as Interactive Systems; 25: Human Factors in XR; 26: Human Factors in XR; 27: Visual Perception & Displays I; 28: Visual Perception & Displays II; 29: Auditory Sense & Immersive Experience; 30: Auditory Sense & Immersive Experience; 31: Other Senses & Full Immersion; 32: Interactive System Development Life Cycle Stages; 33: Introduction to Majuli case study; 34: Introduction to Majuli case study; 35: Usability requirement gathering and specification; 36: Usability requirement gathering and specification; 37: Usability requirement gathering and specification; 38: System Design

## Unit U22: quiz

### Set X

X1. What are the three broad categories of interaction in immersive environments?
   A. object interaction, navigation, and system control
   B. visual, auditory, and haptic interaction
   C. tracking, rendering, and interaction interaction
   D. input, processing, and output interaction
   Marked correct: A
   Explanation: Interaction is broadly categorized into object interaction, navigation, and system control.

X2. In most cases, what kind of occlusion do we deal with for selection?
   A. objects with completely clear visibility
   B. objects with no occlusion at all
   C. entirely occluded or hidden objects
   D. partially occluded or partially visible objects
   Marked correct: D
   Explanation: In the majority of cases, the system deals with partially occluded or partially visible objects.

X3. What does the hand selection technique essentially mean?
   A. selection of virtual objects with the hand
   B. interacting with physical hardware
   C. navigating the user's perspective
   D. managing system-level settings
   Marked correct: A
   Explanation: Hand selection techniques mean selection of virtual objects in the virtual world with the hand.

X4. What does conventional selection with hand refer to?
   A. selection using a handheld controller
   B. selection using a single hand or finger
   C. selection using a virtual hand avatar
   D. selection using both hands simultaneously
   Marked correct: B
   Explanation: Conventionally, selection with hand refers to selection of objects with a single hand or single finger or multiple fingers of a single hand.

X5. How does the prism technique improve upon the go-go technique?
   A. it increases the virtual hand movement speed at high speeds
   B. it allows for a one-to-one mapping at all distances
   C. it enables selection without any physical hand movement
   D. it reduces the physical hand movement speed below a threshold
   Marked correct: D
   Explanation: The prism technique applies scaled-down motion to the virtual hand when the user's hand is moving below a specified speed, making it easier to select distant objects.

X6. How do travel techniques and grabbing techniques differ in object interaction?
   A. travel techniques involve selection while grabbing techniques involve navigation
   B. travel techniques are indirect while grabbing techniques are direct
   C. travel techniques are for system control while grabbing techniques are for manipulation
   D. travel techniques move the hand while grabbing techniques specify the object
   Marked correct: D
   Explanation: Go-go and prism are travel techniques, whereas intent-driven selection is a grabbing technique.

X7. What can a virtual ray consist of in a ray casting technique?
   A. a 2D plane or a volumetric sphere
   B. a short line segment or infinite line
   C. a series of points or a grid of lines
   D. a curved arc or a 3D cone
   Marked correct: B
   Explanation: A virtual ray is defined as a short line segment or an infinite line.

X8. How does the bend cast technique identify the object for selection?
   A. by bending the ray towards the most distant object
   B. by extending the ray until it hits the first object
   C. by calculating the distance to the largest object
   D. by bending the ray towards the closest object
   Marked correct: D
   Explanation: In the bend cast technique, the system bends the ray towards the object closest to the path.

X9. How does the depth ray technique help when a ray hits multiple targets?
   A. by selecting the object that is the largest among the targets
   B. by automatically selecting the object with the highest priority
   C. by bending the ray towards the object at the center
   D. by using a depth marker to select the object closest to it
   Marked correct: D
   Explanation: The depth ray technique uses a depth marker to disambiguate between objects; the object closest to the marker and intersected by the vector is selected.

X10. How does the cone casting flashlight technique differ from basic ray casting?
   A. it selects objects based on the speed of the movement
   B. it selects objects within a 2D plane
   C. it selects all objects within a 3D cone
   D. it selects only the object closest to the ray
   Marked correct: C
   Explanation: Instead of a ray, a cone is used, and objects within the cone get selected.

X11. What is bimanual selection?
   A. using both hands to define a 3D region
   B. using both hands to manipulate a system menu
   C. using both hands to move a single object
   D. using both hands to navigate the virtual world
   Marked correct: A
   Explanation: Two-handed volumetric selection, also called bimanual selection, uses both hands to define a region of the 3D space.

X12. What is the purpose of indirect manipulation?
   A. manipulating the physical hand to move a virtual hand
   B. manipulating a desired object without directly interacting with it
   C. manipulating the user's view to see distant objects
   D. manipulating the system menus to change the environment
   Marked correct: B
   Explanation: Indirect manipulation allows users to manipulate virtual objects without directly interacting with them by interacting with other objects mapped to the desired object.

### Set Y

Y1. Object interaction can be broadly divided into which two types?
   A. Selection and Manipulation
   B. Navigation and Casting
   C. Pointing and Framing
   D. Direct and Indirect
   Marked correct: A
   Explanation: The transcript states that object interactions are broadly of two types: interaction for selection and interaction for manipulation.

Y2. In conventional hand selection techniques, what kind of mapping is typically used for a virtual hand?
   A. One-to-one mapping
   B. Many-to-one mapping
   C. No mapping
   D. Inverse mapping
   Marked correct: A
   Explanation: The virtual hand is tied to the user's physical hand with a direct one-to-one mapping of hand motion.

Y3. What is a major problem with using standard hand selection for objects located far away?
   A. The virtual hand disappears
   B. It requires tiring and annoying physical hand movement
   C. The object changes color
   D. The navigation system stops
   Marked correct: B
   Explanation: Selecting a distant object using a standard virtual hand requires long physical hand movements, which can be tiring and annoying.

Y4. How does the 'go-go' technique help with selecting distant objects?
   A. It makes the object larger
   B. It allows the user to change the virtual arm length
   C. It highlights the object in red
   D. It automatically moves the user to the object
   Marked correct: B
   Explanation: The go-go technique allows the user to interactively change the virtual arm length, mapping smaller physical movements to larger virtual ones as distance increases.

Y5. What is a primary disadvantage of the 'go-go' technique when selecting small distant objects?
   A. Low precision
   B. High computational cost
   C. No visual feedback
   D. The hand moves too slowly
   Marked correct: A
   Explanation: Because the hand moves faster when the object is farther away, the go-go technique can suffer from low precision, making it easy to miss small objects.

Y6. Besides the hand, what other body parts can be used to control a pointing ray?
   A. Head and eye gaze
   B. Feet and legs
   C. Shoulders and elbows
   D. None, only hands are used
   Marked correct: A
   Explanation: The lecture mentions head movement and eye gaze (via trackers) as ways to extend and control the pointing ray.

Y7. What is the purpose of the 'depth marker' in the 'depth ray' technique?
   A. To show the speed of the hand
   B. To disambiguate between multiple objects intersected by a ray
   C. To change the color of the ray
   D. To increase the distance of the object
   Marked correct: B
   Explanation: The depth marker helps the system identify which object the user intends to select when a ray crosses multiple targets.

Y8. Which volumetric selection technique casts a sphere onto the nearest intersected surface?
   A. Cone casting
   B. Sphere casting
   C. Box selection
   D. Ray casting
   Marked correct: B
   Explanation: Sphere casting is described as casting a sphere onto the nearest intersected surface to select objects within it.

Y9. Which of the following are properties that can be modified during object manipulation?
   A. Position, orientation, scale
   B. Color, texture, behavior
   C. All of the above
   D. None of the above
   Marked correct: C
   Explanation: The lecture lists position, orientation, scale, shape, color, texture, and behavior as properties that can be modified during manipulation.

Y10. What is an example of a 2D widget used for indirect manipulation?
   A. A 3D handle
   B. A scroll bar
   C. A virtual hand
   D. A depth marker
   Marked correct: B
   Explanation: The lecture uses a scroll bar as an example of a 2D widget used to indirectly manipulate a page.

Y11. Which characteristic defines the 'spindle' bimanual manipulation technique?
   A. Asymmetric and asynchronous
   B. Symmetric and synchronous
   C. Asymmetric and synchronous
   D. Symmetric and asynchronous
   Marked correct: B
   Explanation: The spindle technique is described as a symmetric synchronous bimanual technique where hands move simultaneously around an imaginary axis.

Y12. In the 'depth ray' technique, how is the depth marker typically controlled?
   A. By moving the hand forwards or backwards
   B. By clicking a button
   C. By moving the head
   D. By blinking the eyes
   Marked correct: A
   Explanation: The user can control the position of the depth marker by moving the hand forwards or backwards.

### Set Z

Z1. Why can the virtual hand technique become annoying when the selected object is far away?
   A. The physical hand must stop for a long time before the virtual grab occurs
   B. The virtual arm must lengthen for a long time before the virtual grab occurs
   C. The physical hand must move for a long time before the virtual grab occurs
   D. The proximity sphere must shrink for a long time before the virtual grab occurs
   Marked correct: C
   Explanation: The virtual hand follows the physical hand closely, so reaching a distant object can require a long real hand movement. The other options describe effects of other techniques, not the basic virtual hand.

Z2. How does the go-go technique make a distant virtual object easier to reach?
   A. It maps smaller physical hand movements to the same virtual hand movements as distance grows
   B. It maps smaller physical hand movements to slower virtual hand movements as distance grows
   C. It maps smaller physical hand movements to stopped virtual hand movements as distance grows
   D. It maps smaller physical hand movements to faster virtual hand movements as distance grows
   Marked correct: D
   Explanation: Go-go increases virtual hand movement for smaller physical hand movements as the target gets farther, reducing the real movement needed to reach it. A one-to-one or reduced mapping would not provide that reaching benefit.

Z3. In intent-driven selection, what does the posture of the virtual fingers indicate?
   A. The user's finger position around an object
   B. The user's confidence in selecting an object
   C. The user's physical distance from an object
   D. The user's physical speed toward an object
   Marked correct: B
   Explanation: Finger posture expresses the user's confidence in the intended target, helping refine the selection. It is not a measure of physical distance, physical speed, or the finger position itself.

Z4. Why is a small distant object hard to select with basic ray casting?
   A. A depth marker selects the object closest to it
   B. The virtual ray must be aimed at the object precisely
   C. The virtual ray bends toward the closest selectable object
   D. The head-mounted display moves the ray with eye movement
   Marked correct: B
   Explanation: Basic ray casting selects the first object intersected by the ray, so a small distant target demands precise aiming, especially when nearby objects compete for that intersection. Bending the ray is bend cast, and a depth marker belongs to depth ray.

Z5. When does bend cast work best?
   A. When many objects are near the ray's path at similar distances
   B. When the user points with the eye instead of the hand
   C. When the intended object is closest to a user-controlled depth marker
   D. When only a few objects are near the ray's path
   Marked correct: D
   Explanation: Bend cast chooses the closest selectable object, so it works best when few objects are near the ray and the intended object is likely the closest. Many nearby objects with similar distances can make the intended object not be the closest, and depth markers or eye pointing are different methods.

Z6. What is a likely trade-off of hand-based manipulation in XR?
   A. The need for more processing or costlier hardware
   B. The need for tracking the user's sense organs
   C. The need for selecting objects in a 3D region
   D. The need for estimating the user's initial registration
   Marked correct: A
   Explanation: Hand manipulation can require more computational power or specialized devices, which may be relatively costly. Registration, volumetric selection, and sense-organ tracking are separate XR concerns.

Z7. In an indirect object-manipulation technique, how does the user's physical hand affect a virtual object?
   A. By moving a separate object that is mapped to it
   B. By moving both controllers symmetrically around it
   C. By moving a virtual hand that reaches it
   D. By framing it on a view plane
   Marked correct: A
   Explanation: Indirect manipulation works through intermediary objects that are mapped to the target, so the user moves a mapped object rather than the target itself. A virtual hand or bimanual controllers act on the target or through a different direct/bimanual technique, and framing on a view plane is a selection method.

Z8. Why can several 3D widgets be needed for one virtual object?
   A. Because each widget is linked to a separate physical prop for the object
   B. Because each widget handles a small set of degrees of freedom for the object
   C. Because each widget requires a separate image-plane selection of the object
   D. Because each widget represents a separate miniature model of the whole object
   Marked correct: B
   Explanation: A 3D widget is usually responsible for only a small set of manipulation degrees of freedom, so different widgets may be used for different object properties. Miniature models, physical props, and image-plane selection belong to other techniques or to selection rather than to the normal reason for using multiple widgets.

Z9. For a distant object, what does a small handheld model of the virtual environment let the user do?
   A. Move the whole virtual environment around in that model
   B. Reach the distant virtual object's body in that model
   C. Select the distant virtual object itself in that model
   D. Manipulate the object's representation in that model
   Marked correct: D
   Explanation: A world-in-miniature model represents objects in a small handheld form, so a distant object can be acted on through its representation without reaching or selecting the distant object itself. The model is not used to move the entire environment, and it does not require the user to reach the object by hand.

Z10. Why can the spindle technique require a lot of practice?
   A. Asymmetric hand movement
   B. Asynchronous hand movement
   C. Single-controller hand movement
   D. Synchronous hand movement
   Marked correct: D
   Explanation: The spindle technique can be hard to use efficiently because it requires the two hands to move synchronously while interacting. Asynchronous movement is a different bimanual pattern, and spindle uses two controllers rather than one.

Z11. In HOMER, which part is moved to the selected object when the ray intersects it?
   A. The physical controller is moved to the object
   B. The ray is moved to the object
   C. The virtual hand is moved to the object
   D. The selection cursor is moved to the object
   Marked correct: C
   Explanation: In HOMER, the virtual hand automatically moves to the object and attaches to it when the ray intersects the desired object. The ray is the pointing element, but it is not the part that attaches to the object.

Z12. Why can augmented reality use regular interaction techniques while immersive environments need improved ones?
   A. AR blocks the user's senses, whereas immersive environments do not block them in the ideal case
   B. AR blocks sensory stimuli, whereas immersive environments supply them freely in the ideal case
   C. AR depends on familiar controls, whereas immersive environments replace them in the ideal case
   D. AR does not block the user's senses, whereas immersive environments do in the ideal case
   Marked correct: D
   Explanation: In augmented reality, the user's senses are not blocked, so ordinary interaction techniques remain usable. Immersive environments, by contrast, aim to block the senses and cut off the real world, so improved interaction techniques are needed.

### Set W

W1. What is the primary focus of navigation as a category of interaction?
   A. Interacting with objects to change their properties
   B. Moving between points with a change in viewpoint
   C. Selecting objects from a set in the world
   D. Setting up the system and its parameters
   Marked correct: B
   Explanation: Navigation is specifically defined as moving from one point in the virtual world to another with a corresponding change in viewpoint, whereas the other options describe object interaction or system control.

W2. What variables influence the choice of an object selection technique to maximize performance?
   A. The cybersickness levels, matched zones, and surface properties
   B. The distance, direction, size, and density of the targets
   C. The navigation paths, resource requirements, and geometric meshes
   D. The visual perception, sensory stimuli, and real-time conditions
   Marked correct: B
   Explanation: Selection performance is maximized by considering variables like the distance, direction, size, and density of the target objects relative to the user's viewpoint.

W3. Why is the prism technique often a better solution than the go-go technique for selecting distant objects?
   A. it maps smaller movements to larger virtual hand movements
   B. it provides faster virtual hand movements
   C. it uses a one-to-one mapping for the virtual hand
   D. it can stop or slow the virtual hand
   Marked correct: D
   Explanation: The prism technique is an improvement over the go-go technique because it can stop or slow the virtual hand, a feature not present in the go-go technique.

W4. What category do the go-go and prism techniques belong to?
   A. travel techniques
   B. grabbing techniques
   C. pointing techniques
   D. manipulation techniques
   Marked correct: A
   Explanation: The go-go and prism techniques are categorized as travel techniques, while intent-driven selection is categorized as a grabbing technique.

W5. How can a user perform pointing-based selection if hand tracking is unavailable?
   A. by using a handheld input device
   B. by using head pointing or eye-gaze pointing
   C. by using a virtual hand
   D. by using a trigger on a controller
   Marked correct: B
   Explanation: The system can use head position or eye gaze to extend the virtual ray when hand tracking is unavailable.

W6. How does volumetric selection differ from image-plane selection?
   A. Volumetric selection selects multiple objects, while image-plane selection is a single object selection technique
   B. Volumetric selection targets a 3D region, while image-plane selection is a 2D view plane selection technique
   C. Volumetric selection uses a sphere or cone, while image-plane selection is a ray selection technique
   D. Volumetric selection is a bimanual method, while image-plane selection is a unimodal selection technique
   Marked correct: B
   Explanation: Fact [2] defines image-plane selection as a two-dimensional (2D) technique, while fact [9] states that volumetric selection enables the selection of a three-dimensional (3D) region.

W7. What happens during object manipulation in an XR system?
   A. translation of a user's pose into virtual motion
   B. modifying properties after selection
   C. registering a sensor's initial position
   D. framing an object in a 2D image plane
   Marked correct: B
   Explanation: Object manipulation is the process of changing an object's properties, such as its position or scale, typically after it has been selected.

W8. What is a potential drawback of using hand manipulation?
   A. more power or specialized devices
   B. less intuitive than indirect manipulation
   C. limited to a two-dimensional view plane
   D. complex multi-step registration process
   Marked correct: A
   Explanation: Hand manipulation may require more computational power or specialized, potentially costly devices; however, it is actually considered the most intuitive manipulation method.

W9. Why might a single 3D widget be insufficient for manipulating all properties of a virtual object?
   A. Widgets are placed in the matched zone
   B. Widgets are used to manipulate distant objects
   C. Each widget handles a small set of degrees of freedom
   D. Widgets require a physical prop linked to neurological data
   Marked correct: C
   Explanation: 3D widgets are typically responsible for only a small set of manipulation degrees of freedom, so multiple widgets are often needed to manipulate all properties of an object.

W10. What distinguishes a World in Miniature (WIM) model from a general indirect proxy?
   A. It allows the user to manipulate a physical prop linked to neurological data
   B. It provides a handheld model of the environment
   C. It is used for objects in the matched zone
   D. It requires the user to interact with a 3D widget placed in the scene
   Marked correct: B
   Explanation: While a general indirect proxy might involve a physical prop linked to neurological data, WIM specifically provides a handheld miniature model of the environment.

W11. How does the spindle-plus-wheel technique differ from the spindle technique?
   A. It is an asymmetric but asynchronous technique
   B. It is a symmetric but synchronous technique
   C. It is an asymmetric but synchronous technique
   D. It is an asynchronous but synchronous technique
   Marked correct: C
   Explanation: While the spindle technique is symmetric, the spindle-plus-wheel technique is an asymmetric but still synchronous extension of it.

W12. How does the HOMER technique handle the virtual hand once a manipulation job is finished?
   A. It leaves the hand attached to the object
   B. It returns the object to its original pose
   C. It returns the hand to its original position
   D. It maintains the hand in the final manipulated pose
   Marked correct: C
   Explanation: After the user indicates the job is done via a trigger or gesture, the virtual hand returns to its original position.

## Unit U23: recap

### Set X

X1. Point: Interaction categories are broadly divided into object interaction, navigation, and system control.

X2. Point: Object interaction is subdivided into selection and manipulation techniques.

X3. Point: Users must be made aware of fully occluded objects to interact with them effectively.

X4. Point: Hand selection involves using a virtual hand avatar that maps to the user's physical hand.

X5. Point: While go-go handles distance, it can sometimes result in low precision for small objects.

X6. Point: Intent-driven selection uses finger postures as an indicator of selection confidence.

X7. Point: The first object intersected by a ray is typically selected through a user-controlled trigger.

X8. Point: Ray pointing can be executed using hand, head, or eye gaze inputs.

X9. Point: Bend cast improves ray casting by automatically bending the ray toward the closest object.

X10. Point: Image plane selection is also referred to as occlusion or framing.

X11. Point: The lifting palm technique involves positioning the palm as if trying to lift an object.

X12. Point: Volumetric selection allows users to select 3D regions in space rather than individual points.

### Set Y

Y1. Point: Target occlusion can affect selection: partially occluded targets can need specialized techniques, and fully occluded targets require user awareness.

Y2. Point: Pointing-based selection uses a short or infinite ray from a hand, head, or eye; sometimes gaze aims and hand triggers.

Y3. Point: Bend cast bends the ray to the closest selectable object, reducing aiming precision, but works best with few nearby objects.

Y4. Point: Depth ray adds a hand-positioned depth marker to choose the intersected object closest to that marker.

Y5. Summary text: Pointing-based selection uses a visible ray from a hand, head, or eye, with a trigger selecting the first intersected object. The ray may be short or infinite, and gaze can aim while the hand triggers. Ray casting is basic but can be imprecise for small distant objects, so bend cast bends the ray toward a closest object when few are nearby, and depth ray uses a depth marker to choose among intersected objects.

Y6. Point: Hand manipulation may need somewhat more computational power or specialized devices that may be relatively costly.

Y7. Point: Indirect manipulation controls virtual objects by manipulating mapped objects, not by manipulating the virtual objects with the physical hand.

Y8. Point: 3D widgets are scene controls; each typically handles a small set of degrees of freedom, so several may be used.

Y9. Point: World-in-miniature is a miniature proxy model, where manipulating a model object moves the corresponding virtual object, both nearby and distant.

Y10. Point: A bimanual manipulation technique uses both hands, with synchronous or asynchronous hand movement.

Y11. Point: The spindle technique is not easy because synchronous hand movement in a virtual world requires practice to use efficiently.

Y12. Summary text: Integrated hybrid manipulation describes techniques that automatically move from selection to manipulation and back without an explicit user signal. HOMER applies this idea by combining ray-casting selection with hand manipulation. When the ray selects an object, HOMER attaches the user's virtual hand to the object, enables hand manipulation of its position and orientation, and ends with a trigger or specific gesture that returns the hand to its original position.

### Set Z

Z1. Point: Interaction is categorized into object interaction, navigation, and system control.

Z2. Point: System control interactions are typically of a regular type used for options and menus.

Z3. Point: Interaction for manipulation involves changing the properties of a selected object.

Z4. Point: Partially occluded objects may require specialized selection techniques.

Z5. Point: Hand selection involves using the hand to select objects in a virtual world.

Z6. Point: Virtual hands can be implemented using 3D tracked controllers.

Z7. Point: The go-go technique maps smaller real movements to larger virtual movements as the distance increases.

Z8. Point: Intent-driven selection uses the posture of virtual fingers as an indication of the user's confidence in selection.

Z9. Point: Bend cast provides circular arc feedback and works best when few objects are near the ray's path.

Z10. Point: Volumetric selection enables users to select 3D regions like boxes, spheres, or cones.

Z11. Point: Cone casting selects objects within a cone, while sphere casting selects objects within a sphere on the nearest intersected surface.

Z12. Point: Indirect proxies link physical props to virtual data for more natural grasping during direct manipulation.

### Set W

W1. Point: System control is a mostly regular interaction for setup and options, unlike object manipulation, object interaction, and navigation.

W2. Point: Object interaction consists of selection and manipulation, which usually employ separate interaction techniques.

W3. Point: Hand selection techniques include virtual hand, go-go, prism, and intent-driven selection for reaching out to trigger a grab.

W4. Point: Intent-driven selection is a grabbing technique using finger postures and proximity spheres that can be combined with travel techniques.

W5. Point: Some methods combine gaze pointing to estimate a target with hand pointing to trigger selection.

W6. Summary text: Pointing-based selection techniques start with basic rays derived from hand, head, or eye movements. Basic ray casting, which can be difficult for small targets, is contrasted with more advanced methods like bend cast and depth ray. These improvements offer ways to handle precision issues and disambiguate multiple objects in a virtual environment.

W7. Point: Volumetric selection is most useful for isolated objects in simple environments but becomes problematic for small objects in complex environments.

W8. Summary text: Indirect manipulation involves controlling virtual objects by interacting with mapped objects rather than the virtual objects themselves. 3D widgets and indirect proxies are techniques for this, with 3D widgets handling a small set of degrees of freedom. World in miniature (WIM) is a type of indirect proxy that allows manipulation of objects both within and outside reach, but is often impractical for large environments.

W9. Summary text: Bimanual manipulation involves using both hands synchronously or asynchronously to manipulate objects. The spindle technique is a symmetric synchronous bimanual technique using two controllers to move or rotate virtual objects, though it can be difficult to use because it requires synchronous hand movements. Spindle plus wheel is an asymmetric synchronous extension of the spindle technique where hands move together without needing symmetric placement.

W10. Summary text: HOMER is an integrated hybrid manipulation technique that combines ray casting selection with hand manipulation. The system automatically attaches the virtual hand to an object upon ray intersection and then switches to a manipulation mode for changing the object's position and orientation. The process ends when a trigger or gesture returns the hand to its original position.

W11. Point: Navigation techniques are interaction techniques for moving from one point to another in a virtual world.

W12. Summary text: Augmented reality systems allow for regular interaction techniques because the user's senses are not blocked, whereas immersive environments require improved techniques because they block the senses and cut off the real world. These improved techniques include object selection and manipulation for virtual objects and navigation techniques for moving through a virtual world. System control interaction, however, primarily relies on regular techniques familiar from other computer systems.

## Unit U24: open question

### Set X

X1. Question: Why might the prism technique be easier to control than the go-go technique when selecting a small distant virtual object?
   Reference answer: The prism technique is easier to control because slowing or stopping the physical hand slows or stops the virtual hand, which go-go cannot do. Go-go maps smaller physical movements to larger, faster virtual movements as distance increases, so a distant small target can be missed or bypassed. Prism scales down virtual motion when the hand is slow and keeps the virtual hand still below a minimum speed.

X2. Question: Why might depth ray be more reliable than bend cast when several objects are close to the path of a virtual ray?
   Reference answer: Depth ray is more reliable in that case because the user can choose depth explicitly, while bend cast relies on closeness to the ray. Bend cast bends toward the closest selectable object by point-line distance, so several nearby objects of similar distances can make the intended object not the closest. Depth ray uses a user-controlled depth marker to disambiguate multiple intersected objects and select the one closest to the marker.

X3. Question: How does Hand-Centered Object Manipulation Extending Ray Casting combine selection and manipulation into one continuous interaction?
   Reference answer: It reduces separate actions by automatically moving from selection to manipulation once a ray selects the object. Selection and manipulation mostly use separate techniques. HOMER mixes ray casting with hand manipulation and switches automatically without an explicit signal; when the ray intersects the object, the virtual hand moves to and attaches to it.

X4. Question: Why is world in miniature less practical for large and complex virtual environments even though it can manipulate distant virtual objects?
   Reference answer: World in miniature becomes less practical for large and complex virtual environments because creating the miniature model is very difficult. The technique provides a miniature handheld model that represents all objects in the virtual environment. Manipulating an object in that model manipulates the corresponding actual object, even outside the user's reach, but that complete model is hard to create when the environment is large and complex.

### Set Y

Y1. Question: What specific environmental parameters should a designer consider when determining which selection technique is most suitable for a virtual experience?
   Reference answer: A designer should consider the distance of the object from the viewpoint, its direction, the size of the object, the density of surrounding objects, the number of targets to be selected, and the level of target occlusion (whether an object is partially or fully hidden).

Y2. Question: Compare the 'go-go' technique and the 'prism' technique for interacting with distant objects. What is the primary trade-off between them?
   Reference answer: The go-go technique allows users to reach distant objects by mapping small physical hand movements to larger, faster virtual hand movements, but it suffers from low precision because the hand moves too quickly to accurately select small targets. The prism technique improves on this by scaling down the motion when the user's hand moves slowly, providing better precision for selecting distant objects at the cost of a non-one-to-one mapping between real and virtual movement.

Y3. Question: When would a designer choose 'indirect manipulation' techniques, such as 3D widgets or 'World in Miniature' (WIM), over direct hand manipulation?
   Reference answer: Indirect manipulation is useful when direct interaction is difficult or costly. 3D widgets are used to control specific degrees of freedom (like a scroll bar) without moving the entire object. 'World in Miniature' is particularly useful for manipulating objects that are outside of the user's reach in the virtual world, as it provides a handheld model that the user can interact with to affect distant objects.

Y4. Question: How does the HOMER technique simplify the interaction flow between selecting and manipulating an object?
   Reference answer: HOMER (Hand-Centered Object Manipulation Extending Ray Casting) integrates selection and manipulation by combining ray casting with hand manipulation. When a user casts a ray that intersects an object, the virtual hand automatically moves to and attaches to that object. This removes the need for the user to perform two separate actions (selecting then grasping), making the transition from pointing to manipulation seamless.

### Set Z

Z1. Question: How does the prism technique improve upon the go-go technique when selecting distant objects?
   Reference answer: The prism technique provides a better solution for selecting distant objects because it allows the virtual hand to stop when the physical hand stops. It achieves this by applying scaled-down motion to the virtual hand when the user's physical hand moves below a specified speed.

Z2. Question: What are the trade-offs between hand manipulation and using three-dimensional widgets for object manipulation?
   Reference answer: Hand manipulation is the most intuitive way of manipulating objects but requires somewhat more computational power or specialized devices. In contrast, three-dimensional widgets are a simple indirect manipulation technique where each widget is typically responsible for only a small set of degrees of freedom.

Z3. Question: How does the Hand-Centered Object Manipulation Extending Ray Casting (HOMER) technique simplify the transition from object selection to object manipulation?
   Reference answer: HOMER integrates selection and manipulation so the user does not need to perform them separately. When a ray intersects a desired object, the virtual hand automatically moves to and attaches to it, and the system switches automatically to manipulation mode.

### Set W

W1. Question: How does the prism technique improve upon the go-go technique for selecting distant objects in a virtual environment?
   Reference answer: The prism technique improves on the go-go technique by applying scaled-down motion to the virtual hand when the user's hand moves below a specified speed. This allows the user to control the movement more effectively and provides a better solution for selecting distant objects because it reduces the physical hand movement speed, which can be easier to control than the high-speed movements of the go-go technique.

W2. Question: How do the bend cast and depth ray techniques address different challenges associated with basic ray casting?
   Reference answer: Bend cast reduces precision problems by bending the ray towards the object closest to the path, so the user does not need to point precisely at the target. Depth ray addresses the problem of disambiguation when a ray intersects multiple targets by using a depth marker to indicate which object is intended for selection.

W3. Question: How do 3D widgets and World in Miniature (WIM) differ in their approach to indirect manipulation?
   Reference answer: 3D widgets put controls directly in the 3D scene, where each widget is typically responsible for only a small set of manipulation degrees of freedom. World in Miniature provides a handheld model of the virtual environment, allowing the user to manipulate objects within and outside of their reach by interacting with the miniature representation of those objects.

W4. Question: In what way does the HOMER technique simplify the transition between selection and manipulation?
   Reference answer: The HOMER technique integrates the two processes by using a ray casting technique to select an object and then automatically moving and attaching the user's virtual hand to that object. This allows the user to switch to manipulation mode instantly without providing an explicit signal to the system.

## Unit U25: odd one out

### Set X

X1. Items: Virtual hand technique | Go-go technique | Spindle technique | Prism technique
   Marked odd: Spindle technique
   Reason: Virtual hand, go-go, and prism are hand selection techniques, while the spindle technique is a bimanual manipulation technique.

X2. Items: Hand manipulation | Bimanual manipulation | Indirect manipulation | Integrated hybrid manipulation
   Marked odd: Integrated hybrid manipulation
   Reason: Hand manipulation, indirect manipulation, and bimanual manipulation are manipulation techniques, while integrated hybrid manipulation is a technique that switches between selection and manipulation.

X3. Items: Spindle technique | Virtual hand technique | Synchronous | Asynchronous
   Marked odd: Spindle technique
   Reason: Synchronous and asynchronous describe hand movement in bimanual manipulation, while the spindle technique is a bimanual manipulation technique.

### Set Y

Y1. Items: Cone | Ray | Sphere | Box
   Marked odd: Ray
   Reason: Box, sphere, and cone are volumetric selection regions; a ray is used in pointing-based selection.

Y2. Items: Head crusher technique | Lifting palm technique | Sticky finger technique | Go-go technique
   Marked odd: Go-go technique
   Reason: Head crusher, sticky finger, and lifting palm are image plane selection techniques; go-go is a hand selection technique.

### Set Z

Z1. Items: Go-go technique | Prism | Intent-driven selection | 3D widgets
   Marked odd: 3D widgets
   Reason: Go-go, Prism, and Intent-driven selection are all techniques for object selection, whereas 3D widgets are a type of indirect manipulation technique.

Z2. Items: Spindle | World in Miniature | HOMER | Depth ray
   Marked odd: Depth ray
   Reason: Spindle, World in Miniature, and HOMER are manipulation techniques, whereas Depth ray is a pointing-based selection technique.

Z3. Items: Head pointing | Eye gaze pointing | Hand pointing | Image plane selection
   Marked odd: Image plane selection
   Reason: Head pointing, Eye gaze pointing, and Hand pointing are specific types of pointing-based selection, whereas Image plane selection is a separate category of selection techniques.

### Set W

W1. Items: Indirect proxies | 3D widgets | World in miniature | Hand manipulation
   Marked odd: Hand manipulation
   Reason: 3D widgets, indirect proxies and world in miniature are indirect manipulation techniques; hand manipulation is a direct manipulation technique.

W2. Items: Depth ray | Bend cast | Ray casting | Hand pointing
   Marked odd: Hand pointing
   Reason: Ray casting, bend cast and depth ray are pointing-based techniques; hand pointing is a method of pointing using a body part.

W3. Items: Image plane selection | Sphere casting | Cone casting | Two-handed box selection
   Marked odd: Image plane selection
   Reason: Cone casting, sphere casting and two-handed box selection are volumetric selection techniques; image plane selection is a 2D selection technique.

## Unit U26: put in order

### Set X

X1. Title: Order the stages of the HOMER interaction technique
   1. Select a target object using a ray casting method
   2. Move and attach the virtual hand to the selected object
   3. Modify properties like position and orientation in manipulation mode
   4. Provide a gesture or trigger to signal the completion of the manipulation
   5. Return the virtual hand to its original position

### Set Y

Y1. Title: Order the stages of HOMER object manipulation
   1. The pointing ray intersects the object
   2. The virtual hand attaches to the object
   3. The virtual hand manipulates the object
   4. The system switches to selection mode

### Set Z

(no items: this system made none)

### Set W

W1. Title: The HOMER Technique Process
   1. Cast a virtual ray towards a desired virtual object
   2. Detect the intersection between the ray and the object
   3. Automatically move the virtual hand to attach to the object
   4. Switch from selection mode to manipulation mode
   5. Modify the object's properties such as position or orientation
   6. Provide a trigger or specific hand gesture to signal the completion of the manipulation
   7. Return the virtual hand to its original position

## Unit U27: concept map

### Set X

X1. interaction --is considered in the design of--> immersive experience

X2. system control --is one of three broad categories of--> interaction

X3. distance --is the distance of the--> target object

X4. density --is the density of objects around the--> target object

X5. object selection technique --in a virtual world includes--> image plane selection

X6. virtual hand technique --is a simplest and most intuitive kind of--> hand selection technique

X7. ray casting --requires precise pointing of the--> virtual ray

X8. head crusher technique --encloses the desired object in a two-dimensional--> image plane

X9. hand manipulation --requires somewhat more--> computational power

X10. spindle plus wheel --is an extension of--> spindle technique

X11. spindle plus wheel --does not require hands to be symmetrically placed around the sides of--> imaginary axis

X12. navigation technique --is for moving from one point to another in a--> virtual environment

### Set Y

Y1. Interaction Techniques --is a kind of--> Navigation

Y2. Interaction Techniques --is a kind of--> Interaction for System Control

Y3. Object Selection --is a kind of--> Pointing-based Selection

Y4. Object Selection --is a kind of--> Image Plane Selection

Y5. Hand Selection --uses--> Virtual Hand

Y6. Hand Selection --is a kind of--> Intent-driven Selection

Y7. Pointing-based Selection --is a kind of--> Ray Casting

Y8. Image Plane Selection --is a kind of--> Framing Hands

Y9. Volumetric Selection --is a kind of--> Two-handed Box Selection

Y10. Object Manipulation --is a kind of--> Indirect Manipulation

Y11. Object Manipulation --is a kind of--> Integrated Hybrid Manipulation

Y12. Indirect Manipulation --uses--> Local Proxies

### Set Z

Z1. Interaction Techniques in Immersive Experiences --is a category of--> System Control

Z2. Object Selection --is a kind of--> Hand Selection Techniques

Z3. Hand Selection Techniques --includes--> Prism Technique

Z4. Pointing-based Selection Techniques --is a kind of--> Ray Casting

Z5. Pointing-based Selection Techniques --is a kind of--> Head Pointing

Z6. Pointing-based Selection Techniques --is a kind of--> Eye Gaze Pointing

Z7. Image Plane and Volumetric Selection --is a kind of--> Image Plane Selection

Z8. Object Manipulation --is a kind of--> Hand Manipulation

Z9. Object Manipulation --is a kind of--> Bimanual Manipulation

Z10. Indirect Manipulation --includes--> 3D Widgets

Z11. Indirect Manipulation --includes--> Indirect Proxies

Z12. Bimanual Manipulation --is a kind of--> Spindle plus Wheel

## Unit U28: recall

### Set X

X1. Prompt: What is XR?
   Answer: XR (Extended Reality) is an umbrella term that encompasses Virtual Reality (VR), Augmented Reality (AR), and Mixed Reality (MR).
   Taught in: lecture 1 (General Intro to XR)

X2. Prompt: What is VR Hardware?
   Answer: VR Hardware refers to the physical devices used to experience virtual reality, such as Head-Mounted Displays (HMDs), controllers, and tracking sensors.
   Taught in: lecture 13 (VR Hardware)

X3. Prompt: What is Tracking?
   Answer: Tracking is the process of monitoring the position, orientation, and movement of the user's body parts (like head, hands, and eyes) in real-time within a virtual environment.
   Taught in: lecture 16 (Understanding Tracking I)

X4. Prompt: What is VR Software?
   Answer: VR Software refers to the applications, engines, and code used to create virtual worlds, render 3D objects, and manage the logic for user interactions.
   Taught in: lecture 19 (VR Software)

X5. Prompt: What is an XR Interactive System?
   Answer: An interactive system in XR allows users to perform actions and receive feedback from a digital environment, facilitating communication between the human and the computer.
   Taught in: lecture 23 (XR as Interactive Systems)

X6. Prompt: What are Usability Requirements?
   Answer: Usability requirements are specifications that define how well a system should perform and how easily it should be used by the target audience to achieve specific goals.
   Taught in: lecture 35 (Usability requirement gathering and specification)

### Set Y

Y1. Prompt: What is interaction?
   Answer: Interaction is the activity that takes place between a user and a system, often by manipulating an image or parts of it with input devices. In immersive environments it is broadly categorized into object interaction, navigation, and system control.
   Taught in: lecture 23 (XR as Interactive Systems)

Y2. Prompt: What is degree of freedom?
   Answer: Degree of freedom is an indication of the different ways an object can move in space; in 3D space, an object can have six degrees of freedom: three translational degrees of freedom along the x, y, and z axes, and three rotational degrees of freedom called yaw, roll, and pitch.
   Taught in: lecture 28 (Visual Perception & Displays II)

Y3. Prompt: What is six degrees of freedom?
   Answer: Six degrees of freedom is the total of six freedoms an object can have in three-dimensional space, consisting of three rotational freedoms called yaw, roll, and pitch, and three translational freedoms along the x, y, and z axes.
   Taught in: lecture 28 (Visual Perception & Displays II)

Y4. Prompt: What is object interaction?
   Answer: Object interaction is a kind of interaction in immersive virtual environments that involves selecting one or more virtual objects in the environment and manipulating a selected object to change its properties.
   Taught in: lecture 38 (System Design)

Y5. Prompt: What is navigation?
   Answer: Navigation is an interaction in an immersive virtual world that moves the user from one point to another by changing the user's viewpoint, mostly without object interaction, and has two components: locomotion and wayfinding.
   Taught in: lecture 38 (System Design)

Y6. Prompt: What is augmented reality system?
   Answer: An augmented reality system is a system with four required characteristics: it enhances the real world with computer-generated digital content registered in 3D, that content is experienced through the user's sensory organs, and it supports real-time interaction with that content in the enhanced environment.
   Taught in: lecture 5 (Definitions)

### Set Z

Z1. Prompt: What is a 3D tracked controller?
   Answer: A hardware device that tracks its position and orientation in 3D space, allowing users to perform natural movements in a virtual environment.
   Taught in: lecture 13 (VR Hardware)

Z2. Prompt: What is eye tracking?
   Answer: A technology that monitors the movement of the user's eyes to determine their point of focus, used for gaze-based interaction.
   Taught in: lecture 18 (Understanding Tracking II)

Z3. Prompt: What is an interactive system?
   Answer: A system where the user provides input and the system responds with feedback, creating a continuous loop of communication.
   Taught in: lecture 23 (XR as Interactive Systems)

Z4. Prompt: What are human factors in XR?
   Answer: The study of human capabilities and limitations (physical, cognitive, and psychological) to design safer and more usable XR experiences.
   Taught in: lecture 25 (Human Factors in XR)

Z5. Prompt: What is visual perception?
   Answer: The process by which the brain interprets and makes sense of sensory information, such as depth, motion, and object properties.
   Taught in: lecture 27 (Visual Perception & Displays I)

Z6. Prompt: What is system design?
   Answer: The process of defining the architecture, interaction techniques, and guidelines for creating a cohesive immersive experience.
   Taught in: lecture 38 (System Design)
