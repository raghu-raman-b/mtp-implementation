# Lecture 62: Linking theory to practice

Transcript: transcripts/lec_62.txt

Goal: Develop and deploy a marker-based AR prototype in Unity by setting up C# scripting, implementing interactive object behavior, and integrating an AR SDK.

Objectives:
- Explain the need for Unity scripting in customized XR experiences and set up a basic C# scripting environment with a functioning script.
- Create and deploy a basic interactive Unity experience by using C# scripting to control objects, handle events and input, and package the build.
- Integrate an external AR SDK into Unity and configure, build, and run a Vuforia marker-based AR project that displays a 3D model over an image target.

Earlier lectures: 1: General Intro to XR; 2: Application Domains and System Categories; 3: Application Domains and System Categories; 4: Definitions; 5: Definitions; 6: Historical Evolution; 7: Historial Evolution; 8: Issues & Challenges; 9: Issues & Challenges; 10: Cybersickness; 11: Cybersickness; 12: Cybersickness; 13: VR Hardware; 14: VR Hardware; 15: AR Hardware; 16: Understanding Tracking I; 17: Understanding Tracking - I; 18: Understanding Tracking II; 19: VR Software; 20: VR Software; 21: AR Software; 22: AR Software; 23: XR as Interactive Systems; 24: XR as Interactive Systems; 25: Human Factors in XR; 26: Human Factors in XR; 27: Visual Perception & Displays I; 28: Visual Perception & Displays II; 29: Auditory Sense & Immersive Experience; 30: Auditory Sense & Immersive Experience; 31: Other Senses & Full Immersion; 32: Interactive System Development Life Cycle Stages; 33: Introduction to Majuli case study; 34: Introduction to Majuli case study; 35: Usability requirement gathering and specification; 36: Usability requirement gathering and specification; 37: Usability requirement gathering and specification; 38: System Design; 39: System Design; 40: System Design; 41: System Design; 42: System Implementation; 43: System Implementation; 44: System Implementation; 45: System Implementation; 46: System Implementation; 47: System Implementation; 48: System Implementation; 49: VR experience optimisation; 50: VR experience optimisation; 51: VR experience optimisation; 52: VR experience optimisation; 53: VR experience optimisation; 54: VR resource optimization; 55: VR resource optimization; 56: VR resource optimization; 57: VR resource optimization; 58: VR resource optimization; 59: VR resource optimization; 60: Linking theory to practice; 61: Linking theory to practice

## Unit U36: quiz

### Set X

X1. When you install the Unity Hub package, what is automatically installed along with the editor interface?
   A. The Source Code for the game engine
   B. The Unity game engine (middleware)
   C. A full suite of 3D models
   D. A pre-configured server
   Marked correct: B
   Explanation: The transcript mentions that installing the Unity Hub package automatically installs the Unity game engine, which acts as the middleware.

X2. Which IDEs are supported by the Unity Development Environment for scripting?
   A. Visual Studio, Visual Studio Code, and JetBrains Rider
   B. Notepad++ and Sublime Text
   C. Eclipse and NetBeans
   D. Only the built-in Unity Notepad
   Marked correct: A
   Explanation: The transcript specifies that Unity supports IDEs such as Visual Studio, Visual Studio Code, and JetBrains Rider.

X3. What is the primary scripting language supported by Unity?
   A. Python
   B. C++
   C. C#
   D. Java
   Marked correct: C
   Explanation: The script mentioned in the lecture confirms that the scripting language supported by Unity is C#.

X4. What type of programming language is C#?
   A. Functional programming language
   B. Procedural programming language
   C. Object-oriented programming language
   D. Assembly language
   Marked correct: C
   Explanation: The lecturer describes C# as an object-oriented programming language created by Microsoft.

X5. How are scripts typically created within the Unity interface?
   A. Assets > Create > C# Script
   B. File > New > Script
   C. Edit > Create > New Script
   D. Window > Tools > Scripting
   Marked correct: A
   Explanation: The instructor explains that scripts are created by going to Assets, then Create, then C# Script from the main menu.

X6. Which class is typically inherited by the class you are defining in a Unity script?
   A. BaseClass
   B. MonoBehaviour
   C. GameObject
   D. ScriptableObject
   Marked correct: B
   Explanation: The lecture mentions that the MonoBehaviour class is typically inherited by the class defined in the script.

X7. How often is the 'Update' function invoked?
   A. Once at the beginning of the game
   B. In each frame
   C. Every 5 seconds
   D. Only when a collision occurs
   Marked correct: B
   Explanation: The Update function is invoked in each frame of the execution.

X8. What is the purpose of the 'Vector3' data type in Unity scripting?
   A. To represent a 3D point with three coordinates
   B. To store a list of 3D models
   C. To define a 3D color
   D. To represent a vector of 3 strings
   Marked correct: A
   Explanation: The lecturer says Vector3 can be used to represent a position of a 3D point, capturing three coordinates.

X9. If a script calls 'Destroy(gameObject, 5f)', what happens?
   A. The object is destroyed instantly
   B. The object is destroyed after 5 seconds
   C. The object is hidden for 5 seconds
   D. The script stops running for 5 seconds
   Marked correct: B
   Explanation: The lecture explains that Destroy(gameObject, 5f) means the game object is destroyed from the scene after 5 seconds.

X10. Which of the following are examples of initialization events in Unity?
   A. Update, FixedUpdate, LateUpdate
   B. Start and Awake
   C. OnMouseDown, OnMouseOver
   D. OnCollisionEnter, OnTriggerEnter
   Marked correct: B
   Explanation: The lecture identifies Start and Awake as initialization events.

X11. Which programming constructs are supported by scripts for conditional logic?
   A. if-else statements
   B. switch-case statements only
   C. Only nested loops
   D. No conditional logic is supported
   Marked correct: A
   Explanation: The lecturer mentions that the scripting environment supports conditional or if-else statements.

X12. What is the purpose of the 'InvokeRepeating' function?
   A. To stop all scripts immediately
   B. To invoke a method at a specific time and then repeatedly every specified second
   C. To create a loop that never ends
   D. To change the platform of the build
   Marked correct: B
   Explanation: InvokeRepeating invokes a method at a specific time, then repeatedly, every specified second.

### Set Y

Y1. Why would a developer use the scripting support in the Unity Development Environment?
   A. To decrease the software's file size
   B. To create a more customized experience
   C. To avoid using the editor interface
   D. To improve the hardware performance
   Marked correct: B
   Explanation: Scripting provides a way for programmers to customize the experience beyond what is built-in.

Y2. What is the scripting language used by Unity?
   A. Python
   B. Java
   C. C#
   D. Ruby
   Marked correct: C
   Explanation: The scripting language supported by Unity is C#.

Y3. What type of programming language is C#?
   A. A procedural programming language
   B. An object-oriented programming language
   C. A low-level assembly language
   D. A functional programming language
   Marked correct: B
   Explanation: C# is an object-oriented programming language created by Microsoft.

Y4. What happens when a C# script is attached as a component to a game object?
   A. It prevents the object from moving
   B. It can control the object's behavior
   C. It deletes the object from the scene
   D. It automatically scales the object
   Marked correct: B
   Explanation: Attaching a script as a component allows a developer to control the behavior or activities of that game object.

Y5. Which interface can be used to check variable values?
   A. The Project panel interface
   B. The Inspector interface
   C. The Build Settings interface
   D. The Console interface
   Marked correct: B
   Explanation: You can check the variable values using the Inspector interface on the Unity Hub editor.

Y6. How can a developer see a message printed by the Debug.Log function?
   A. On the console output
   B. In the Project panel
   C. In the Inspector interface
   D. In the file's properties
   Marked correct: A
   Explanation: The Debug.Log function prints a message on the console output after the script is executed.

Y7. What are event functions?
   A. Functions activated by the user manually in response to inputs
   B. Functions activated by Unity in response to gameplay events
   C. Functions used to create new files and manage the project structure
   D. Functions that manage the hardware and optimize the performance
   Marked correct: B
   Explanation: Event functions are activated by Unity in response to events that occur during gameplay.

Y8. How does Unity handle control during an event function?
   A. It keeps control of the main thread
   B. It blocks all other script execution
   C. It passes control to the event function body
   D. It automatically deletes the function
   Marked correct: C
   Explanation: Unity passes control to an event function when an event happens, the body is executed, and then control is passed back to Unity.

Y9. What programming constructs handle logic branches?
   A. Looping constructs
   B. Memory pointers
   C. Array structures
   D. Conditional statements
   Marked correct: D
   Explanation: Conditional statements (like if-else) are supported by scripts to handle different logic paths.

Y10. What is the difference between for/while loops and do-while loops?
   A. The speed at which they execute
   B. The amount of memory they use
   C. The number of times they repeat
   D. The timing of the condition check
   Marked correct: D
   Explanation: For and while loops are entry-controlled (checked at the beginning), while do-while loops are exit-controlled (checked at the end).

Y11. What is the primary use of the transform property?
   A. To store and manipulate network, ID, and type
   B. To store and manipulate physics, weight, and speed
   C. To store and manipulate position, rotation, and scale
   D. To store and manipulate color, texture, and opacity
   Marked correct: C
   Explanation: The transform property is used to store and manipulate the position, rotation, and scale of an object.

Y12. How does scripting affect the complexity of customizing an XR system?
   A. It removes the need for any programming
   B. It involves more programming for customization
   C. It only works with basic systems
   D. It simplifies the coding of every feature
   Marked correct: B
   Explanation: Scripting involves more programming and is necessary for a customized experience.

### Set Z

Z1. Why does a programmer write C# scripts for a customized experience in Unity?
   A. To change the built-in support
   B. To create a new type of game object
   C. To compile scripts in an integrated development environment
   D. To install the scripting environment
   Marked correct: A
   Explanation: Unity's built-in support provides only the behavior that the environment already has, so scripts are written to change that behavior for a customized experience. Installing the environment or compiling scripts are setup steps, not the reason for writing a script.

Z2. In a Unity script, how does Vector3 represent the position of a 3D point?
   A. It stores an orientation as vector elements
   B. It stores three coordinates as vector elements
   C. It stores a pose as vector elements
   D. It stores two coordinates as vector elements
   Marked correct: B
   Explanation: Vector3 represents a 3D point by storing its three coordinates as the three elements of a vector.

Z3. What is the result of calling Destroy(gameObject, 5f) in Unity?
   A. the game object is created again in the scene after five seconds
   B. the script is no longer running in the scene after five seconds
   C. the scene is paused in the editor after five seconds
   D. the game object is no longer in the scene after five seconds
   Marked correct: D
   Explanation: In Unity, Destroy with a delay removes the game object from the scene after the specified number of seconds. A delay of 5f means the object disappears five seconds after the call.

Z4. What do Unity's OnCollision event functions relate to?
   A. a script being called as the starting point
   B. contact being made or broken
   C. a game object disappearing after a delay
   D. a collider being configured as a trigger
   Marked correct: B
   Explanation: OnCollision event functions relate to contact being made or broken. A collider configured as a trigger is associated with OnTrigger-type functions, not OnCollision functions.

Z5. What distinguishes a do-while loop from a for or while loop?
   A. The condition is checked before the body executes
   B. The condition is checked until the body executes
   C. The condition is checked after the body executes
   D. The condition is checked while the body executes
   Marked correct: C
   Explanation: A do-while loop is exit-controlled: the body runs first and the condition is checked afterward, so the body executes at least once. A for or while loop is entry-controlled, checking the condition before the body can run.

Z6. When a Unity project uses an input device beyond the mouse, keyboard, and buttons, what role does imported SDK input support play?
   A. A requirement for the mouse, keyboard, and buttons
   B. A replacement for Unity's inbuilt input support
   C. An extension of Unity's inbuilt input support
   D. A setting that starts the build process
   Marked correct: C
   Explanation: For device-specific inputs not covered by Unity's inbuilt handling, imported SDK input support can be used to extend that support. It does not replace the built-in handling for mouse, keyboard, and buttons, nor does it start the build.

Z7. After a script is written and a Unity system is built, what is the last stage in the Unity development environment?
   A. Editing the scripts for the scenes
   B. Importing SDK input support
   C. Publishing or deploying the system
   D. Rebuilding the system again
   Marked correct: C
   Explanation: Once the script is written and the system is built, the final stage is to publish or deploy it. Importing SDK support, rebuilding, or editing scripts are development steps that come before that final publication stage.

Z8. In the Unity Build Settings window, what does the platform section determine?
   A. The start of the build process
   B. The input devices supported by scripts
   C. The deployment target for the system
   D. The scenes included in the build
   Marked correct: C
   Explanation: The platform section selects the platform to which the system is deployed. The scenes are managed by the Scenes in Build panel, the build is started by the Build or Build and Run button, and input support is handled by scripting and SDK input support.

Z9. Why does a developer import a platform-specific SDK into Unity?
   A. To use Unity functions that the platform's built-in support lacks
   B. To use platform functions that Unity's built-in support includes
   C. To use platform functions that Unity's built-in support lacks
   D. To use application functions that the platform's built-in support lacks
   Marked correct: C
   Explanation: Importing an external SDK lets the developer use platform functions that Unity's built-in support does not provide. The reversed options mistake which side supplies the missing functions.

Z10. In the Unity sample, how does adding the Vuforia SDK extend the built-in environment?
   A. It adds recognition of real-world images and objects
   B. It adds markerless placement of virtual objects in the scene
   C. It adds a built-in 3D modeling tool for assets
   D. It adds access to device-specific sensor and input data
   Marked correct: A
   Explanation: Vuforia extends Unity by supplying image-recognition functionality, i.e., recognizing images and objects in the real world. Access to device-specific sensory or input data is the role of other platform-specific SDKs, not Vuforia.

Z11. When the Android platform is selected in the sample, what does Build and Run do?
   A. It creates a database package and uploads it to the Vuforia website
   B. It creates an APK and installs it on the connected Android device
   C. It creates a scene file and copies it to the Android device
   D. It creates a 3D model and assigns it to the image target
   Marked correct: B
   Explanation: Build and Run packages the Unity project as an Android APK and deploys it to the connected device. It does not generate the marker database, the 3D model, or a standalone scene file.

Z12. What allows a basic virtual or augmented reality system to be built with less programming than a customized one?
   A. Hand-written code support for basic functions
   B. Menu-based IDE support for basic functions
   C. Imported SDK support for basic functions
   D. Custom scripting support for basic functions
   Marked correct: B
   Explanation: A basic system can be assembled with menu-based IDE support without scripting, while a customized experience requires scripting and therefore more programming. SDKs are not the reason a basic system needs less code.

### Set W

W1. How are C# scripts usually created within the Unity editor?
   A. Through the external 2D asset import process
   B. Through the graphics pipeline configuration
   C. Through the AR visualization tool interface
   D. Through the Assets, Create, C# Script menu
   Marked correct: D
   Explanation: Scripts are typically created directly within the Unity environment using the Assets menu.

W2. What does the Vector3 data type store in a Unity script?
   A. the orientation of a viewer
   B. the position of a 3D point
   C. the movement of a 2D object
   D. the name of a scene object
   Marked correct: B
   Explanation: The Vector3 data type represents the position of a three-dimensional (3D) point by storing three coordinates.

W3. What is required to instantiate a prefab at runtime and how is this configuration established in the editor?
   A. A public class and creating a new prefab within the script's namespace
   B. A transform property and dragging the prefab into the hierarchy window
   C. A MonoBehaviour script and dragging the prefab into the scene view
   D. A script reference and dragging the prefab into the My Prefab field
   Marked correct: D
   Explanation: To instantiate a prefab at runtime, the script needs a reference to it, which is set by dragging the prefab from the project window into the script component's 'My Prefab' field.

W4. How do for loops and do-while loops differ in their control structure?
   A. The for loop handles arrays while the do-while loop handles individual data types
   B. The for loop is a synchronous operation while the do-while loop is a coroutine
   C. The for loop executes at least once while the do-while loop may not execute at all
   D. The condition is checked before the body for for loops and after the body for do-while loops
   Marked correct: D
   Explanation: For and while loops are entry-controlled because the condition is checked before the body executes; do-while loops are exit-controlled because the body executes at least once before the condition is checked.

W5. How does using a foreach loop change how a programmer interacts with collections of homogeneous data types?
   A. It automatically optimizes the resource requirements for the computer graphics pipeline by handling lighting and shading
   B. It allows the programmer to spread tasks across multiple frames by pausing execution and returning control to Unity
   C. It allows the programmer to work with the collection directly instead of dealing with individual data types
   D. It automatically simulates the physical forces and collisions for each item in the collection via a physics engine
   Marked correct: C
   Explanation: A foreach loop allows the programmer to work with a collection directly rather than having to manage individual data types within that collection.

W6. Why must a gradual opacity fade be implemented as a coroutine rather than a single function call?
   A. it allows the opacity value to be reset every frame
   B. it allows the script to access the graphics card directly
   C. it allows the change to be spread across multiple frames
   D. it prevents the application from freezing during the fade
   Marked correct: C
   Explanation: A single function call happens instantly in one frame, which is not perceivable; a coroutine is needed to spread the change across multiple frames.

W7. Which parameters are required for InvokeRepeating to trigger a method?
   A. a function name, an initial delay, and a repeat interval
   B. a function name and a total number of repetitions
   C. a function name and a specified priority level
   D. a function name and a total duration of the task
   Marked correct: A
   Explanation: InvokeRepeating requires three arguments: the name of the function to call, the initial delay before the first call, and the interval at which it repeats.

W8. How are inputs from specific devices like data gloves handled in Unity when they are not natively supported?
   A. Using the transform property
   B. Using inbuilt handling of inputs
   C. Using a coroutine for input processing
   D. Using an imported SDK
   Marked correct: D
   Explanation: Unity handles basic inputs like mouse and keyboard internally, but specific device inputs require an imported software development kit (SDK).

W9. When does an image target behavior script execute its operations in the sample project?
   A. while the Vuforia engine is identifying the image
   B. before the Vuforia engine recognizes the marker
   C. immediately after the project is deployed
   D. after the Vuforia engine recognizes the marker
   Marked correct: D
   Explanation: The image target behavior script is designed to perform operations specifically after the Vuforia engine recognizes the marker.

W10. Why are specific settings, such as removing Vulkan and using the OpenGL API, configured in the Unity player settings for this project?
   A. they are application-specific
   B. they are standard for XR
   C. they are required for Android
   D. they are required for Vuforia
   Marked correct: A
   Explanation: These settings are application-specific and may not work for other projects or platforms.

W11. What determines the amount of programming required to build an XR system?
   A. the complexity of the visual assets
   B. the variety of user inputs
   C. the specific hardware platform
   D. the required functionality
   Marked correct: D
   Explanation: The amount of programming depends on the required functionality, with basic systems needing less and customized experiences requiring more.

W12. How can a basic XR system be built without using scripts?
   A. using a web-based platform
   B. using pre-built scene templates
   C. using a drag-and-drop editor
   D. using menu-based IDE support
   Marked correct: D
   Explanation: A basic system with basic functionalities can be built without scripting using menu-based integrated development environment (IDE) support.

## Unit U37: recap

### Set X

X1. Point: C# scripts can be attached as components to game objects to control their behavior.

X2. Point: Scripts allow developers to trigger events, modify properties, and respond to user input.

X3. Point: Scripts are placed in the folder selected in the project panel.

X4. Point: The class name must be the same as the script's file name.

X5. Point: The Inspector interface allows developers to check variable values.

X6. Point: Instantiating prefabs at runtime requires a reference to the prefab.

X7. Point: The foreach loop is used for collections of homogeneous data types.

X8. Point: Coroutines allow spreading tasks across frames on the main thread.

X9. Point: InvokeRepeating calls a method at a specific time and repeats it every specified second.

X10. Point: Editor build settings allow managing scenes, platforms, and publishing the system.

X11. Point: SDKs are used to access platform-specific features not provided by the built-in Unity support.

X12. Summary text: Linking theory to practice involves utilizing the Unity development environment's scripting and SDK support. Developers can use C# scripts to create custom behaviors beyond built-in features and integrate external SDKs for platform-specific capabilities. This workflow enables the creation and deployment of customized immersive systems on various hardware platforms.

### Set Y

Y1. Point: The Unity Hub package automatically installs the Unity game engine, which serves as the system's middleware.

Y2. Point: While Unity provides built-in support, scripting is necessary for a more customized and specific experience.

Y3. Point: Unity supports several IDEs, including Visual Studio, Visual Studio Code, and JetBrains Rider.

Y4. Point: C# scripts can be attached to game objects as components to control their activities and properties.

Y5. Point: Creating a script in Unity is essentially creating a new custom component type.

Y6. Point: In a C# script, the class name must be identical to the file name.

Y7. Point: Most Unity scripts inherit from the MonoBehaviour class.

Y8. Point: Variables and data types, such as Vector3, are used to store and represent 3D coordinates.

Y9. Point: The Unity Inspector interface allows developers to monitor and modify variable values visually.

Y10. Point: Standard programming constructs like if-else statements are supported for conditional logic.

Y11. Point: Coroutines are not threads and continue to execute on the main thread.

Y12. Point: The InvokeRepeating function allows a method to be called repeatedly at specific time intervals.

### Set Z

Z1. Point: A Unity C# script defines namespaces, a public class inheriting from MonoBehaviour, and a name matching its file.

Z2. Point: Developers can view code, check variable values in the Inspector, and see messages in the console output.

Z3. Summary text: Unity C# scripts are structured as public classes using Start and Update functions to manage execution. They utilize data types like Vector3 for 3D positions, while the Unity editor provides tools to inspect the code, variables, and console output.

Z4. Summary text: Unity scripts use prebuilt and user-defined functions to control game objects and manage gameplay. A specific prebuilt function, the Destroy function, allows for removing objects from the scene after a specified delay. Unity also utilizes event functions, which are triggered by gameplay events to execute logic and produce realistic physical or interactive behaviors.

Z5. Point: To instantiate a prefab at runtime, the script must have a reference to that prefab.

Z6. Point: For and while loops are entry-controlled, while do-while loops are exit-controlled based on when the condition is checked.

Z7. Point: Coroutines allow a developer to spread tasks across several frames by pausing execution and returning control to Unity.

Z8. Point: The SDK layer is positioned on top of the Unity layer and is treated as part of the installed package.

Z9. Point: Vuforia is an AR SDK primarily meant for computer vision tasks such as object detection, recognition, and tracking.

Z10. Point: External packages like Vuforia are required because Unity’s built-in support for computer vision is not extensive.

Z11. Summary text: Vuforia is a cross-platform SDK that extends Unity with image recognition and device-specific data access. Project setup involves licensing, creating a recognition database, and configuring the scene with cameras, targets, and 3D models. The process concludes with configuring specific graphics and architecture settings to build and deploy the application to Android.

Z12. Summary text: Building and deploying VR and AR systems are programming tasks where the required functionality determines the level of scripting needed. When functionality exceeds the support provided by the Unity development environment, SDKs provide necessary device-specific support. Furthermore, the Programmer's and Developer's Manuals offer additional details for building, deploying, and writing code for these systems.

### Set W

W1. Point: A Unity script has Start called as its starting point and Update called in each frame during execution.

W2. Point: Unity's MonoBehaviour Destroy function destroys a game object from the scene after a delay specified in seconds.

W3. Point: Unity scripts use prebuilt functions and user-defined functions, with user-defined functions typically part of a good script.

W4. Point: Unity event functions are activated by gameplay events, including update, initialization, graphical user interface, collision, and trigger functions.

W5. Point: For and while are entry-controlled loops, and do-while is exit-controlled, running at least once before checking.

W6. Point: A gradual opacity fade must be defined as a coroutine and started so its opacity changes over several visible frames.

W7. Summary text: Unity's interactive scripting and build deployment work together. Scripting handles built-in mouse, keyboard, and button inputs, while imported SDKs may extend support for device-specific inputs. After the script is written and the system is built, the Build Settings window supports publishing by managing included scenes, selecting the target platform, and starting the build.

W8. Point: If a specified hardware platform offers functions not in Unity, the developer imports an SDK or package to use them.

W9. Point: Vuforia is an AR SDK primarily for object recognition and computer vision tasks such as detection, recognition, and tracking.

W10. Summary text: External SDKs are imported when a specified hardware platform provides functions that Unity's built-in support does not include. In Unity's layered architecture, the SDK layer sits above Unity and below the application, and its package APIs are used. Vuforia is an AR SDK for object recognition, an area where Unity's built-in support is not extensive or good, so the integration steps are to install Unity Hub, import the SDK, use Unity and SDK functions, then compile, build, and deploy.

W11. Point: For Android, application-specific Unity player settings are set, then the APK is built and run to the device.

W12. Point: The Programmer's Manual and Developer's Manual on the respective websites give further details on building, deploying, and writing XR code.

## Unit U38: open question

### Set X

X1. Question: Why is scripting needed for a customized Unity experience even though menu-based integrated development environment support can build a basic system?
   Reference answer: Menu-based IDE support can build a basic system without scripting, but Unity's built-in support provides only the experience the system already provides. A C# script attached as a component to a game object gives the developer a component that behaves as desired rather than according to the built-in support, so a customized experience requires writing such scripts.

X2. Question: Why must a gradual opacity fade in Unity be implemented as a coroutine rather than as a function called once?
   Reference answer: A gradual opacity fade is visible only when the opacity value is reduced over a sequence of frames so Unity renders the intermediate values. A coroutine can pause execution, return control to Unity, and continue on the following frame, so the change can be spread frame by frame. A function called once cannot produce that visible fade.

X3. Question: Why does the marker-based augmented reality sample use Vuforia instead of relying only on Unity's built-in support?
   Reference answer: Unity's built-in support for object recognition, computer vision, object detection, and tracking is not extensive or very good. Vuforia is an augmented reality software development kit primarily meant to help developers deal with object recognition or computer vision issues, such as object detection, recognition, and tracking. Its setup requires a database containing the marker images, so the Vuforia engine can recognize the marker and display the three-dimensional model in place of the marker.

### Set Y

Y1. Question: Why is scripting required for building a customized augmented reality (from lecture 1) experience in the Unity development environment?
   Reference answer: Scripting is required because Unity's built-in support only provides a standard quality experience. To obtain a more customized experience according to the programmer's expectations and needs, the programmer must write scripts or small pieces of code to change the built-in support.

Y2. Question: Why must a gradual opacity fade of an object be implemented as a coroutine?
   Reference answer: A fade function called only once is not perceivable, so the change must be spread frame by frame. A coroutine allows a developer to spread tasks across several frames by pausing execution, returning control to Unity, and continuing where it left off on the following frame.

Y3. Question: How does the integration of a software development kit (SDK) like Vuforia affect the architecture and capabilities of a Unity-based augmented reality (from lecture 1) system?
   Reference answer: Integrating an SDK adds a software development kit layer on top of the Unity layer, which provides application programming interfaces. This extends the built-in environment to provide platform-specific functions and advanced functionality like image recognition which is not extensively provided by Unity's built-in support.

### Set Z

Z1. Question: How does writing scripts allow a developer to create a more customized experience than using the built-in support provided by the Unity environment?
   Reference answer: Scripts provide a way to change the built-in support provided by the system to meet specific needs and expectations. By attaching a script as a component to a game object, a developer can control the behavior of that object, allowing them to trigger game events, modify component properties over time, and respond to user input as they wish.

Z2. Question: Why is a coroutine used instead of a single function call to create a perceivable fading effect for an object's opacity?
   Reference answer: A single function call for fading may not be perceivable because it is only called once. A coroutine allows a developer to spread a task across several frames by pausing execution and returning control to Unity, which makes the gradual change in opacity perceivable.

Z3. Question: How can a developer incorporate external SDKs to overcome the limitations of the built-in Unity environment?
   Reference answer: Developers import SDK packages to access specific functions and functionalities provided by platforms that are not part of the built-in support provided by the Unity environment. This allows the developer to use the functions and advantages of both the Unity environment and the SDK.

### Set W

W1. Question: How does the concept of attaching a C# script as a component differ from using Unity's built-in editor support in terms of developer experience?
   Reference answer: Unity's built-in support provides a standard, pre-configured experience suitable for common tasks, but it is limited to the functionalities provided by the engine. By attaching a script as a component, a developer creates a customized experience where they can trigger specific game events, modify properties over time, and respond to user inputs in a way that is uniquely tailored to their specific needs rather than relying on the system's default behavior.

W2. Question: Explain the distinction between a standard function and a coroutine when performing a time-sensitive task like fading an object's opacity, and why this distinction is critical for VR/AR applications.
   Reference answer: A standard function executes its logic in a single frame, which might happen so quickly that the transition (like a fade) is not perceivable by the user. A coroutine, however, allows a developer to spread a task across several frames by pausing execution and returning control to Unity. In immersive environments like VR/AR, this is critical for creating smooth, perceivable visual transitions and animations that occur over time.

W3. Question: How does the integration of an SDK (like Vuforia) illustrate the layered architecture of a virtual or augmented reality system?
   Reference answer: The integration of an SDK illustrates the layered architecture by placing a specialized software layer between the Unity engine and the underlying hardware/libraries. While Unity provides the core environment (middleware), an SDK provides specific, advanced functionalities (like computer vision or device-specific sensors) that are not part of the built-in support. This allows developers to bridge the gap between high-level application logic and low-level hardware capabilities without having to write the foundation-level code from scratch.

## Unit U39: odd one out

### Set X

X1. Items: OnTriggerExit function | OnTriggerEnter function | OnTriggerStay function | OnCollisionEnter function
   Marked odd: OnCollisionEnter function
   Reason: OnTriggerEnter function, OnTriggerStay function, and OnTriggerExit function are physics-related events; OnCollisionEnter function is a physics event function.

X2. Items: OnMouseOver function | OnCollisionEnter function | OnMouseDown function | OnGUI function
   Marked odd: OnCollisionEnter function
   Reason: OnGUI function, OnMouseOver function, and OnMouseDown function are graphical user interface event functions; OnCollisionEnter function is a physics event function.

X3. Items: OnGUI function | FixedUpdate function | LateUpdate function | Update function
   Marked odd: OnGUI function
   Reason: Update function, FixedUpdate function, and LateUpdate function are regular update event functions; OnGUI function is a graphical user interface event function.

### Set Y

Y1. Items: C# | Visual Studio | Python | JetBrains Rider
   Marked odd: Python
   Reason: The lecture identifies C#, Visual Studio, and JetBrains Rider as part of the scripting support for Unity, but it does not mention Python as a supported language.

Y2. Items: Start | Awake | Update | Debug.Log
   Marked odd: Debug.Log
   Reason: Start, Awake, and Update are categorized in the lecture as Unity event functions, whereas Debug.Log is a standard function used for printing messages to the console.

Y3. Items: Vuforia | DirectX | OpenGL | Vulkan
   Marked odd: Vuforia
   Reason: DirectX, OpenGL, and Vulkan are mentioned as low-level libraries supported by Unity, while Vuforia is described as an external SDK for AR functionality.

### Set Z

Z1. Items: FixedUpdate function | Start function | Update function | LateUpdate function
   Marked odd: Start function
   Reason: Update, FixedUpdate, and LateUpdate are regular update event functions, while Start is an initialization event function.

Z2. Items: OnCollisionStay function | OnTriggerEnter function | OnCollisionEnter function | OnCollisionExit function
   Marked odd: OnTriggerEnter function
   Reason: OnCollisionEnter, OnCollisionStay, and OnCollisionExit are physics event functions, whereas OnTriggerEnter is a physics-related event function for trigger colliders.

Z3. Items: Scale | Opacity | Rotation | Position
   Marked odd: Opacity
   Reason: Position, rotation, and scale are the properties stored by a Unity transform property, while opacity is an alpha value used for fading.

### Set W

W1. Items: Start function | Update function | LateUpdate function | FixedUpdate function
   Marked odd: Start function
   Reason: Update function, FixedUpdate function, and LateUpdate function are regular update events; Start function is an initialization event.

W2. Items: OnCollisionExit | OnCollisionStay | OnCollisionEnter | OnTriggerEnter
   Marked odd: OnTriggerEnter
   Reason: OnCollisionEnter, OnCollisionStay, and OnCollisionExit are physics events; OnTriggerEnter is a trigger event.

W3. Items: OnMouseDown | OnGUI | OnMouseOver | Awake
   Marked odd: Awake
   Reason: OnGUI, OnMouseOver, and OnMouseDown are GUI events; Awake is an initialization event.

## Unit U40: put in order

### Set X

X1. Title: Order the steps to integrate an SDK with the Unity development environment
   1. Install the Unity Hub
   2. Import the SDK package into the Unity environment
   3. Use the functions provided by both Unity and the SDK
   4. Compile the system
   5. Build the system
   6. Deploy the system

X2. Title: Order the steps to use the Build Settings in Unity
   1. Open the Build Settings window
   2. Manage the scenes in the Build panel
   3. Select the target platform in the Platform section
   4. Select the Build or Build and Run button

### Set Y

Y1. Title: Order the events in Unity event-function activation
   1. An event occurs during gameplay
   2. Unity passes control to the event function
   3. The function body executes
   4. Control returns to Unity

Y2. Title: Order the basic steps of SDK integration in Unity
   1. Unity Hub is installed
   2. The SDK package is imported into the Unity environment
   3. The functions of both Unity and the SDK are used
   4. The system is compiled, built, and deployed

### Set Z

Z1. Title: Process for Creating and Attaching a Script in Unity
   1. Go to the Assets menu and select Create.
   2. Create a new C# script in the project folder.
   3. Double-click the script asset to open and edit the code in the IDE.
   4. Attach the script as a component to a game object.
   5. Execute the game to start the script's behavior.

Z2. Title: Steps to Integrate the Vuforia SDK for AR
   1. Create a new project in the Unity Hub.
   2. Create a Vuforia account and arrange for a license.
   3. Download and import the Vuforia engine into the Unity project assets.
   4. Set up the Vuforia configuration and create a database on the website.
   5. Download and import the database package into the project.
   6. Configure the AR camera and image targets in the sample scene.
   7. Adjust the player settings and build the system for the target device.

### Set W

W1. Title: Order the steps to attach a prefab for runtime instantiation in the Unity editor
   1. Create a new script
   2. Create an empty game object
   3. Add the script to the game object as a component
   4. Create a prefab
   5. Drag the prefab from the project window into the script component's My Prefab field

W2. Title: Order the steps for integrating a software development kit (SDK) into the Unity development environment
   1. Install Unity Hub
   2. Import the SDK package into the Unity environment
   3. Use the functions of both Unity and the SDK
   4. Compile, build, and deploy the system

## Unit U41: concept map

### Set X

X1. Scripting Support --uses--> C# Language

X2. MonoBehaviour Class --contains--> Functions

X3. Functions --includes--> Start Function

X4. Functions --includes--> Event Functions

X5. Functions --includes--> Coroutines

X6. Functions --includes--> InvokeRepeating

X7. Scripting Support --uses--> Variables and Data Types

X8. Scripting Support --supports--> Conditional Statements

X9. Scripting Support --manipulates--> Transform Property

X10. Unity Development Environment --extended by--> SDKs

X11. SDKs --part of--> Layered Architecture

X12. Vuforia SDK --is a kind of--> SDKs

### Set Y

Y1. Linking Theory to Practice --implemented via--> Unity Development Environment

Y2. Unity Development Environment --provides--> Built-in Support

Y3. Unity Development Environment --provides--> Scripting Support

Y4. Built-in Support --comprises--> Unity Editor

Y5. Scripting Support --implemented via--> C# Scripting

Y6. C# Scripting --uses--> Programming Constructs

Y7. C# Scripting --includes--> Unity API

Y8. Unity Development Environment --includes--> Building and Deployment

Y9. SDK Support --example is--> Vuforia SDK

Y10. Vuforia SDK --provides access to--> Platform-specific Features

Y11. Layered Architecture --structures--> Unity Development Environment

Y12. Layered Architecture --contains--> SDK Support

### Set Z

Z1. Unity --supports as its scripting language--> c-sharp

Z2. unity script --is essentially a new type of--> component

Z3. unity script --allows the developer to respond to--> user input

Z4. vector3 --is a--> data type

Z5. unity script --uses--> prebuilt function

Z6. for each loop --can be used for--> collection

Z7. opacity fade --is visible only when its--> opacity

Z8. opacity fade --is spread over a sequence of--> frame

Z9. Build button --begins--> build

Z10. software development kit layer --is positioned on top of--> Unity layer

Z11. Vuforia --supports multiple platforms, including--> Unity

Z12. augmented reality camera --is selected in a sample scene of--> Unity

## Unit U42: recall

### Set X

X1. Prompt: What is System Implementation?
   Answer: System Implementation is the phase in the development life cycle where theoretical designs and requirements are converted into a functional system using software, hardware, and scripting.
   Taught in: lecture 42 (System Implementation)

X2. Prompt: What is Middleware?
   Answer: Middleware is software that acts as a bridge between different applications or the operating system and the final application; in this context, the Unity game engine serves as the middleware.
   Taught in: lecture 19 (VR Software)

X3. Prompt: What is XR as Interactive Systems?
   Answer: XR as Interactive Systems refers to the way users engage with virtual or augmented environments through inputs (such as mouse, keyboard, or buttons) and receive real-time feedback.
   Taught in: lecture 23 (XR as Interactive Systems)

X4. Prompt: What is AR Software?
   Answer: AR Software provides the necessary framework and algorithms, such as computer vision and object recognition, to overlay digital information onto the real world.
   Taught in: lecture 21 (AR Software)

X5. Prompt: What is VR/AR Hardware?
   Answer: VR/AR Hardware includes the physical devices, such as Head-Mounted Displays (HMDs) and various platform-specific sensors, required to experience XR systems.
   Taught in: lecture 13 (VR Hardware)

X6. Prompt: What is Layered Architecture?
   Answer: Layered Architecture is a structural design that organizes an XR system into layers, including the application, the game engine (like Unity), SDKs, libraries (like OpenGL or Vulkan), the operating system, and the physical hardware.
   Taught in: lecture 38 (System Design)

### Set Y

Y1. Prompt: What is System Implementation?
   Answer: The process of translating theoretical requirements and system designs into a functional software or hardware system.
   Taught in: lecture 42 (System Implementation)

Y2. Prompt: What is AR Software?
   Answer: Software that overlays digital information, such as 3D models or interactive elements, onto the physical world in real-time.
   Taught in: lecture 21 (AR Software)

Y3. Prompt: What is Interactive Systems?
   Answer: Systems where users can interact with a digital or physical environment and receive corresponding responses from the system.
   Taught in: lecture 23 (XR as Interactive Systems)

Y4. Prompt: What is System Design?
   Answer: The architectural planning of an XR system, defining its components, behaviors, and overall structure before implementation.
   Taught in: lecture 38 (System Design)

Y5. Prompt: What is Development Life Cycle?
   Answer: The sequence of stages an XR system goes through, including requirements gathering, design, implementation, testing, and deployment.
   Taught in: lecture 32 (Interactive System Development Life Cycle Stages)

Y6. Prompt: What is AR Hardware?
   Answer: Physical devices, such as smart glasses or mobile devices, that enable the display and interaction of augmented reality content.
   Taught in: lecture 15 (AR Hardware)

### Set Z

Z1. Prompt: What is Vuforia?
   Answer: Vuforia is a cross-platform augmented reality (AR) software development kit (SDK) that uses computer vision to recognize and track images and objects in the real world for creating AR applications.
   Taught in: lecture 22 (AR Software)

Z2. Prompt: What is Unity?
   Answer: Unity is a popular cross-platform game engine and developer environment that provides an editor interface and implementation support for the computer graphics pipeline, enabling developers to create, build, and deploy 2D and 3D interactive content, including XR experiences.
   Taught in: lecture 60 (Linking theory to practice)

Z3. Prompt: What is trigger?
   Answer: A trigger is a Unity collider configured using the isTrigger property that does not behave as a solid object and allows other colliders to pass through.
   Taught in: lecture 61 (Linking theory to practice)

Z4. Prompt: What is collider?
   Answer: A collider is a component in a physics engine that defines a game object's shape for physical collisions. It can be static, use primitive or mesh shapes, or be a trigger that other colliders pass through.
   Taught in: lecture 61 (Linking theory to practice)

Z5. Prompt: What is augmented reality (AR)?
   Answer: Augmented reality (AR) is an enhanced version of reality created by technology, in which computer-generated digital content is overlaid on the real world in real time and registered in 3D, so the user perceives and interacts with the enhanced environment.
   Taught in: lecture 1 (General Intro to XR)

Z6. Prompt: What is marker?
   Answer: A marker is a real-world object or image placed in the environment that a system detects to identify its position or track a user's motion and to place digital content at that position.
   Taught in: lecture 3 (Application Domains and System Categories)
