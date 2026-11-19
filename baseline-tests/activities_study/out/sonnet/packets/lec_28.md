# Lecture 28: Visual Perception & Displays II

Transcript: transcripts/lec_28.txt

Goal: Explain how human visual and spatial perception constrain the optics and display requirements of three-dimensional XR systems.

Objectives:
- Describe how an XR headset produces the perception of a three-dimensional virtual environment.
- Explain how human visual-perception constraints determine XR display requirements for spatial resolution, intensity, and temporal resolution.

Earlier lectures: 1: General Intro to XR; 2: Application Domains and System Categories; 3: Application Domains and System Categories; 4: Definitions; 5: Definitions; 6: Historical Evolution; 7: Historial Evolution; 8: Issues & Challenges; 9: Issues & Challenges; 10: Cybersickness; 11: Cybersickness; 12: Cybersickness; 13: VR Hardware; 14: VR Hardware; 15: AR Hardware; 16: Understanding Tracking I; 17: Understanding Tracking - I; 18: Understanding Tracking II; 19: VR Software; 20: VR Software; 21: AR Software; 22: AR Software; 23: XR as Interactive Systems; 24: XR as Interactive Systems; 25: Human Factors in XR; 26: Human Factors in XR; 27: Visual Perception & Displays I

## Unit U15: quiz

### Set X

X1. Why do images of faraway objects focus onto the retina in a normal eye?
   A. The retina serves as a magnifying lens for distant objects
   B. The combined power of the cornea and lens exceeds required power
   C. The lens provides a fixed focal depth for incoming rays
   D. The cornea provides exactly the 40 diopter required power
   Marked correct: B
   Explanation: The combined optical power of the cornea and the natural lens is 60 diopter, which exceeds the 40 diopter required to focus faraway objects onto the retina.

X2. What is the primary role of the common region in binocular vision?
   A. It allows both eyes to see the same image
   B. A region of view restricted to the right eye
   C. A region of view restricted to the left eye
   D. A region of total vision impairment
   Marked correct: A
   Explanation: The common region is where both eyes see the same image, which is a key component of binocular vision.

X3. Which concept specifically explains how the brain generates a 3D view from two 2D images?
   A. Binocular vision
   B. Stereoscopy
   C. Translational motion
   D. Field of view
   Marked correct: B
   Explanation: Stereoscopic vision helps us perceive a 3D view of objects, aided by our binocular vision property.

X4. How do we perceive motion in a virtual world?
   A. Through translational movements along the x y and z axes
   B. Through binocular and stereoscopic vision properties
   C. Through rotational movements involving yaw roll and pitch
   D. Through translational and rotational degrees of freedom
   Marked correct: D
   Explanation: We perceive motion in a virtual world with respect to the degrees of freedom supported, which include both translational and rotational movements.

X5. Which three terms describe the rotational degrees of freedom?
   A. x, y, and z axes
   B. translation, pitch, and roll
   C. yaw, roll, and depth
   D. yaw, roll, and pitch
   Marked correct: D
   Explanation: The three rotational degrees of freedom are yaw, roll, and pitch.

X6. Where should a VR headset's engineered lens be placed relative to the screen for the best experience?
   A. At the point where it intersects the retina
   B. At a distance equal to the screen's diameter
   C. At a distance equal to its focal length
   D. At the minimum possible distance from the eye
   Marked correct: C
   Explanation: To get the best experience, the engineered lens in a VR headset is usually placed at the distance of its focal length from the screen.

X7. What type of image is projected onto the retina in a VR headset?
   A. A real image
   B. A projected 2D image
   C. A reflected image
   D. A virtual image
   Marked correct: A
   Explanation: Even though the screen appears as a virtual image to the user, a real image is nevertheless projected onto the retina.

X8. What is the specific consequence of seeing individual lights when a display is highly magnified?
   A. Aliasing
   B. Screen door effect
   C. Moiré pattern
   D. Jitter
   Marked correct: A
   Explanation: Aliasing is the effect where smooth lines appear jagged or like staircases, often noticed when a display is highly magnified.

X9. What does the "screen door effect" appear as?
   A. A flickering of the pixels
   B. A blur over the objects
   C. A screen on top of the image
   D. A jagged edge on the lines
   Marked correct: C
   Explanation: The screen door effect appears as if there is a screen on top of the image, commonly noticed in images produced by LCD projectors.

X10. Which part of the eye provides the majority of the optical power?
   A. the aqueous fluid
   B. the lens
   C. the cornea
   D. the vitreous fluid
   Marked correct: C
   Explanation: The cornea has an optical power of approximately 40 diopters, while the eye lens is less powerful at approximately 20 diopters.

X11. What is the primary purpose of binocular vision in XR?
   A. Allows for simultaneous 2D processing
   B. Enhances depth perception and 3D relationships
   C. Increases the total horizontal field of view
   D. Reduces the required frame rate
   Marked correct: B
   Explanation: Binocular vision enhances depth perception and the relationship between objects in 3D space.

X12. What is the primary purpose of temporal resolution in VR headset design?
   A. Increasing the total number of pixels
   B. Matching the photoreceptor density
   C. Allowing smooth motion perception without jitter
   D. Enhancing the depth of 3D objects
   Marked correct: C
   Explanation: Temporal resolution, or frame rates, are very important in the context of motion perception to allow us to perceive motion smoothly without jitter.

### Set Y

Y1. Compared with an artificial lens setup, what does light in the human eye pass through after the natural lens?
   A. A second glass lens before the retina
   B. Liquid inside the eye
   C. Air inside the eye
   D. A flat focal plane behind the lens
   Marked correct: B
   Explanation: Light in the eye travels through the liquid interior after passing through the natural lens, whereas light in an artificial lens setup travels through air after the lens. A second glass lens or flat plane is not the medium it passes through.

Y2. What explains the need for high optical power in the human eye?
   A. The wide field of view of the human eye
   B. The curved retinal surface of the human eye
   C. The small outer diameter of the human eye
   D. The liquid-filled interior of the human eye
   Marked correct: C
   Explanation: The eye's short outer diameter means parallel rays must be converged onto the retina with high optical power. Field of view, liquid interior, and retinal curvature are not the reason for that need.

Y3. Why does a VR headset place its screen at the focal length of its engineered lens?
   A. So the screen appears as a flat picture on the headset's front surface
   B. So the screen appears as a real image on the engineered lens
   C. So the screen appears as a small virtual image at a close distance
   D. So the screen appears as an enormous virtual image at infinity
   Marked correct: D
   Explanation: Placing the screen at the engineered lens’s focal length makes the small nearby display appear to the user as a large image at an infinite distance. It does not make the screen appear small and close, nor does it place a visible real image on the lens or headset.

Y4. What is field of view in human vision?
   A. the size of the screen visible to the eye
   B. the number of objects visible to the eye
   C. the distance to the boundary visible to the eye
   D. the angular region visible to the eye
   Marked correct: D
   Explanation: Field of view is the angular region of the scene visible from one point in time. It is not a count of objects, a screen size, or a distance to a boundary.

Y5. What does the region seen by both eyes contribute to depth perception?
   A. A separate image that links objects in 3D space
   B. A common image that links objects in 3D space
   C. A peripheral image that links objects in 3D space
   D. A monocular image that links objects in 3D space
   Marked correct: B
   Explanation: In binocular vision, both eyes see the same image over their common viewing region, and this shared view helps a person understand relationships between objects in 3D space. Areas seen by only one eye are not the shared depth cue.

Y6. How does stereoscopic viewing produce a three-dimensional view?
   A. Simultaneous processing of one 2D image generates a 3D view
   B. Simultaneous processing of two 3D images generates a 3D view
   C. Sequential processing of two 2D images generates a 3D view
   D. Simultaneous processing of two 2D images generates a 3D view
   Marked correct: D
   Explanation: Stereoscopy works because the left and right eyes process their two 2D images at the same time, and that simultaneous processing produces a 3D view. One image, sequential processing, or already-3D source images are not the described mechanism.

Y7. How are the six degrees of freedom of an object in 3D space divided?
   A. 2 rotational, 4 translational
   B. 2 rotational, 2 translational
   C. 3 rotational, 3 translational
   D. 4 rotational, 2 translational
   Marked correct: C
   Explanation: A 3D object has six degrees of freedom: three rotational ones, such as yaw, roll, and pitch, and three translational ones along the x, y, and z axes.

Y8. In a virtual world, perceived motion is tied to what property of the virtual environment?
   A. The supported sensory stimulation
   B. The supported real-time latency
   C. The supported field of view
   D. The supported degrees of freedom
   Marked correct: D
   Explanation: Motion in a virtual world is perceived with respect to the degrees of freedom that the world supports. Other display or system properties may affect the experience, but they are not what motion perception is tied to here.

Y9. What quality target fits a VR display designed around human visual receptors?
   A. Reach the highest quality the display panel can provide
   B. Reach a balanced quality that is cheaper to manufacture
   C. Reach the lowest quality that is still visible
   D. Reach enough quality to fool the visual sense
   Marked correct: D
   Explanation: A display matching human visual performance should reach the level at which the visual sense is fooled; it does not need the highest panel quality, the lowest visible level, or a cost-balanced level.

Y10. In an XR display, which property describes the rate at which pixels change so that movement appears smooth?
   A. Color resolution
   B. Temporal resolution
   C. Spatial resolution
   D. Intensity resolution
   Marked correct: B
   Explanation: Temporal resolution refers to the frame rate or speed at which display pixels change, which is what allows motion to be perceived smoothly. Spatial resolution concerns pixel count per area, and intensity resolution concerns the range of intensity values.

Y11. What condition makes a sharp diagonal line look jagged?
   A. Screen-door grid lines are visible
   B. Individual lights are visible
   C. Frame-rate jitters are visible
   D. Intensity steps are visible
   Marked correct: B
   Explanation: Aliasing appears when individual display lights are visible, making a diagonal line look jagged; the screen-door effect is a separate layered-grid appearance.

Y12. Why is the traditional retina-display pixel-density criterion less suitable for a headset display?
   A. A magnifying lens keeps the display far from the eye
   B. A magnifying lens reduces the field of view for the eye
   C. A magnifying lens brings the display close to the eye
   D. A magnifying lens lowers the needed pixels for the eye
   Marked correct: C
   Explanation: For close-to-eye headset displays, a magnifying lens brings the display close to the eye, so much higher pixel density is probably needed. The other lens effects are not the stated reason the criterion is less suitable.

### Set Z

Z1. What configuration allows a VR headset to present a virtual image at an infinite distance?
   A. Close to eyes to fill the view
   B. At the natural lens' focal length of the eye
   C. At the engineered lens' focal length
   D. At the cornea's refractive index
   Marked correct: C
   Explanation: Placing the screen at the focal length of the engineered lens causes the screen to appear to the user as a virtual image at an infinite distance.

Z2. What is a requirement for a person to perceive the world within a VR headset?
   A. Virtual image on the retina
   B. Real image in the eye
   C. Virtual image in the eye
   D. Real image on the retina
   Marked correct: D
   Explanation: A person does not perceive the world unless real images are formed on the retina, even though the image appears as a virtual image to the user.

Z3. What term is used to describe the region visible to the human eye?
   A. The optical path
   B. The peripheral range
   C. The view frustum
   D. The visual display
   Marked correct: C
   Explanation: Field of view (FOV) is the view frustum, representing the region visible to the human eye at any single point in time.

Z4. What occurs when both eyes are focused on an object at an infinite distance?
   A. They see a full visual range
   B. They see a total 360-degree range
   C. They see a peripheral region
   D. They share a common visual region
   Marked correct: D
   Explanation: In binocular vision, focusing on infinity causes both eyes to see the same image over a common region of approximately 120 degrees.

Z5. What is the core process of stereoscopy?
   A. Both eyes view the same image simultaneously
   B. Each eye views a different image simultaneously
   C. Each eye views an image from a different angle
   D. Each eye views an image from a different distance
   Marked correct: B
   Explanation: Stereoscopy involves two eyes viewing two images simultaneously, where each eye processes its respective image while sharing a common part.

Z6. What is the result of the brain processing two simultaneous 2D images in a stereoscopic system?
   A. The expansion of the horizontal field of view
   B. The generation of a three-dimensional view
   C. The reduction in depth perception
   D. The increase in peripheral vision
   Marked correct: B
   Explanation: Processing simultaneous 2D images from different eyes generates a three-dimensional view of the objects, aided by binocular vision.

Z7. What is the primary purpose of translational movement in a three-dimensional virtual world?
   A. rendering triangular meshes
   B. moving at different angles
   C. providing sensory stimuli
   D. navigating in that space
   Marked correct: D
   Explanation: Translational movement is used for navigating space, while rotational movement is primarily used for moving at different angles along the translational axis.

Z8. Which three components make up the rotational degrees of freedom in three-dimensional space?
   A. the x, y, and z axes
   B. field of view
   C. yaw, roll, and pitch
   D. sensory stimuli
   Marked correct: C
   Explanation: In three-dimensional space, there are three rotational degrees of freedom (yaw, roll, and pitch) and three translational degrees of freedom (x, y, and z axes).

Z9. How is motion perceived by a user in a virtual world?
   A. With respect to the computer-provided sensory stimuli
   B. With respect to the supported degrees of freedom
   C. With respect to the angular measure of the field of view
   D. With respect to the perception of sharp diagonal lines
   Marked correct: B
   Explanation: Motion in a virtual world is perceived with respect to the degrees of freedom that the system supports.

Z10. Why do wearable AR head-mounted displays require a much higher pixels per linear inch (ppi) count than a standard retina display?
   A. the human eye has higher photoreceptor density for close objects
   B. the display needs to show more distinct intensity values
   C. magnifying lenses bring the display close to the eye
   D. the display must provide a much wider field of view
   Marked correct: C
   Explanation: Fact [7] explains that because a magnifying lens brings the display close to the eye, the required ppi is likely 7 to 8 times higher than a standard retina display.

Z11. Besides increasing spatial resolution, what techniques can be used to reduce the screen door effect or aliasing in a VR headset?
   A. decreasing the frame rate and increasing the zoom
   B. adjusting the field of view and using foveated rendering
   C. adjusting the focal depth and increasing brightness
   D. increasing the intensity range and increasing color depth
   Marked correct: B
   Explanation: Fact [8] lists adjusting the field of view and foveated rendering as corrective mechanisms for aliasing or the screen door effect.

Z12. Why do virtual reality headsets require frame rates much higher than standard television or movie standards?
   A. to allow for higher intensity resolution
   B. to prevent perception of jagged diagonal lines
   C. to allow motion to be perceived smoothly
   D. to provide a wider field of view
   Marked correct: C
   Explanation: Fact [9] states that higher frame rates are preferred for motion perception in an immersive environment to allow motion to be perceived smoothly.

### Set W

W1. What is a primary difference between the image surface of the human eye and an engineered lens setup?
   A. The human eye has a planar focal plane.
   B. The human eye has a non-planar retina.
   C. The human eye lacks a refractive index.
   D. The human eye uses air as its primary internal medium.
   Marked correct: B
   Explanation: The transcript specifies that the human eye has a non-planar retina which replaces the concept of a focal plane found in engineered lenses.

W2. Through how many different media does light travel before hitting the retina in the human eye?
   A. 3
   B. 4
   C. 5
   D. 6
   Marked correct: C
   Explanation: The lecture lists five media: air, cornea, aqueous fluid, natural lens, and vitreous fluid.

W3. What is the approximate combined optical power of the cornea and the natural lens in a human eye?
   A. 40 Diopters
   B. 20 Diopters
   C. 60 Diopters
   D. 80 Diopters
   Marked correct: C
   Explanation: The cornea has a power of approximately 40 Diopters and the natural lens has a power of approximately 20 Diopters, totaling 60 Diopters.

W4. In a VR headset, where should the engineered lens ideally be placed relative to the screen for the best experience?
   A. At the very edge of the user's vision.
   B. At the distance of its focal length.
   C. Exactly 24 millimeters from the eye.
   D. At the same plane as the retina.
   Marked correct: B
   Explanation: The lecture states that the distance between the screen and the engineered lens should be the focal distance of the engineered lens to get the best experience.

W5. What is the approximate horizontal field of view (FOV) for the human eye?
   A. 90 degrees
   B. 120 degrees
   C. 150 degrees
   D. 180 degrees
   Marked correct: D
   Explanation: The transcript mentions the human eye has approximately a 180-degree horizontal field of view.

W6. Which of the following are the three rotational degrees of freedom in 3D space?
   A. X, Y, and Z
   B. Yaw, Roll, and Pitch
   C. Depth, Width, and Height
   D. Width, Height, and Time
   Marked correct: B
   Explanation: The lecture identifies Yaw, Roll, and Pitch as the three rotational degrees of freedom.

W7. What does the term 'Degrees of Freedom' indicate in the context of virtual worlds?
   A. The number of pixels on a screen.
   B. The types of textures available in a scene.
   C. The different ways an object can move in space.
   D. The total brightness of the display.
   Marked correct: C
   Explanation: Degrees of freedom are described as an indication of the different ways an object can move in space (e.g., translational and rotational).

W8. What is the term used to describe jagged lines or 'staircase' effects in low-resolution displays?
   A. Screen Door Effect
   B. Foveated Rendering
   C. Aliasing
   D. Stereoscopy
   Marked correct: C
   Explanation: Aliasing is the term used when smooth lines appear jagged due to the limitations of resolution.

W9. What is the 'Screen Door Effect'?
   A. The ability to see 3D depth.
   B. The appearance of a screen on top of an image, commonly noticed in LCD projectors.
   C. The rate at which pixels refresh.
   D. The way light passes through the cornea.
   Marked correct: B
   Explanation: The Screen Door Effect is described as appearing as if there is a screen on top of the image, commonly noticed in images produced by LCD projectors.

W10. What was the recommended pixels per linear inch (PPI) for a 'Retina Display'?
   A. 100 PPI
   B. 200 PPI
   C. 326 PPI
   D. 500 PPI
   Marked correct: C
   Explanation: The lecture mentions that Steve Jobs claimed 326 PPI is enough to achieve a Retina Display.

W11. Why is the standard 'Retina Display' resolution often insufficient for VR headsets?
   A. VR headsets are too small to display many pixels.
   B. Because the display is very close to the eye, requiring 7 to 8 times higher PPI.
   C. The human eye cannot process 326 PPI.
   D. Because VR headsets do not use convex lenses.
   Marked correct: B
   Explanation: Since VR headsets are close to the eye, the PPI requirement is much higher, probably 7 to 8 times higher than what is there in a standard Retina Display.

W12. What is the goal of the artificial system (screen and lens) in a VR headset regarding the human eye?
   A. To replace the natural lens of the eye.
   B. To provide a higher resolution than the human retina.
   C. To convert light into 'normal' light so that the eye perceives a real image on the retina.
   D. To eliminate the need for the optic nerve.
   Marked correct: C
   Explanation: The objective is to make the artificial system work in a way such that it converts light into normal light that falls on the eye so that eventually we get to perceive the image of whatever we are seeing.

## Unit U16: recap

### Set X

X1. Point: Light travels through five different media with distinct refractive indices in the human eye, but not in engineered lenses.

X2. Point: The five media in the human eye include air, cornea, aqueous fluid, natural lens, and vitreous fluid.

X3. Point: The combined optical power of the cornea and lens is 60 diopters, which is more than the 40 diopters required.

X4. Point: To provide the best experience, the VR headset lens is placed at its focal distance to create an enormous virtual image.

X5. Point: The goal of XR displays is to supplement normal eye operation so that real images are formed on the retina.

X6. Point: Binocular vision occurs in a common 120-degree region where both eyes see the same image simultaneously.

X7. Point: Binocular vision enhances depth perception and the understanding of the relationship between objects in 3D space.

X8. Point: Stereoscopy involves using two eyes to view two 2D images simultaneously to generate a 3D view of objects.

X9. Point: The six degrees of freedom in 3D space include three rotational and three translational axes.

X10. Point: XR displays should be designed to match the performance of the human visual sense, specifically concerning spatial, intensity, and temporal resolution.

X11. Point: VR headsets require much higher frame rates than standard televisions to perceive smooth motion without jitter.

X12. Summary text: Human vision physiology and the optical properties of the natural eye are compared with engineered lens setups used in VR headsets. Understanding how humans perceive depth, motion, and field of view determines the specific requirements for spatial and temporal resolution in XR hardware. This knowledge informs the design of systems that supplement normal eye operation so that users perceive images on the retina.

### Set Y

Y1. Point: The human eye has a curved retina instead of a focal plane, and its interior is liquid.

Y2. Point: Light passes through five media; a 24 mm eye would need at least 40 diopters, but its lenses give 60.

Y3. Point: A VR headset uses a close screen and a convex lens to focus screen light on the retina.

Y4. Point: The VR screen appears virtual, but a real image forms on the retina; perception requires real retinal images.

Y5. Summary text: The human eye focuses light on a curved retina through several refractive media, and its cornea plus natural lens provide the optical power needed for that focus. A VR headset uses a nearby screen and a convex lens so that the screen’s light can also form an image on the retina. When the screen is placed at the engineered lens’s focal length, it appears as a huge virtual image at infinity, while a real retinal image still makes perception possible.

Y6. Point: When both eyes focus on infinity, binocular vision shares about 120 degrees, with outer areas seen by one eye.

Y7. Summary text: Field of view defines the angular region visible to the eye at one instant. Binocular vision adds an overlapping shared view from both eyes, which improves depth perception and understanding of 3D object relationships. Stereoscopy uses separate left and right 2D images, processed simultaneously, to produce the perception of 3D objects.

Y8. Point: 3D virtual worlds may allow translational movement for navigation and rotational movement, primarily at different angles along the translational axis.

Y9. Point: In 3D space, an object can have six degrees of freedom: yaw, roll, pitch, and x, y, z translations.

Y10. Point: In a virtual world, motion is perceived with respect to the degrees of freedom that are supported.

Y11. Point: Visible individual display lights can cause jagged lines or a screen-like overlay, known as aliasing or screen door effect.

Y12. Point: Immersive VR motion needs frame rates much higher than ordinary 24 or 60 fps, with higher preferred.

### Set Z

Z1. Point: The lecture bridges the gap between the physiology of vision and the engineering of head-mounted displays.

Z2. Point: The human eye consists of a cornea, a natural lens with variable focal depth, and a non-planar retina.

Z3. Point: Engineered lens systems differ from the human eye by using a planar focal plane and air instead of liquid media.

Z4. Point: A minimum of 40 diopters is required to focus parallel light rays onto the center of the retina.

Z5. Point: VR headsets utilize a convex lens and a screen to create a virtual image that appears infinitely far away.

Z6. Point: The screen in a VR headset should be placed at the focal distance of the engineered lens for the best experience.

Z7. Point: Despite the virtuality of the image, our brains still require real images to be projected onto the retina to perceive them.

Z8. Point: The human eye has a horizontal field of view of approximately 180 degrees and a vertical field of view of 150 degrees.

Z9. Point: Binocular vision allows both eyes to share a common 120-degree region, which is crucial for depth perception.

Z10. Point: Stereoscopy is the process of simultaneously processing two 2D images to generate a 3D view.

Z11. Point: Motion in 3D space is defined by six degrees of freedom: three translational (x, y, z) and three rotational (Yaw, Roll, Pitch).

Z12. Summary text: This lecture explores the intersection of human visual physiology and the engineering of immersive displays like VR headsets. By analyzing how the eye processes light, depth, and motion, the lecture establishes the technical requirements for spatial, temporal, and intensity resolutions needed to create realistic virtual experiences.

### Set W

W1. Point: Field of view (FOV) is the angular measure of the region visible to the human eye at any single moment.

W2. Point: In binocular vision, both eyes focus on a common 120-degree region while seeing outside areas independently.

W3. Point: Binocular vision enhances depth perception and helps a person understand the relationship between objects in three-dimensional space.

W4. Point: Stereoscopic vision, aided by binocular vision, generates a 3D view of objects by processing two 2D images simultaneously.

W5. Summary text: Field of view describes the angular region visible to the human eye at a single point in time. Binocular vision provides depth perception by focusing on a common 120-degree region while seeing outside areas independently. Stereoscopy utilizes binocular vision to generate a 3D view of objects by processing two simultaneous 2D images.

W6. Point: A virtual world may allow translational movement for navigation and rotational movement at different angles along the translational axis.

W7. Point: Degrees of freedom indicate the different ways an object can move in space.

W8. Point: Motion in a virtual world is perceived with respect to the degrees of freedom that are supported.

W9. Summary text: Degrees of freedom represent the ways objects move in 3D space. Identifying the specific rotational and translational components of these degrees of freedom clarifies how the movements supported by a virtual world relate to the user's perception of motion.

W10. Point: Engineering requirements for VR displays should match the performance of the human visual sense.

W11. Point: Matching human vision involves spatial resolution, intensity resolution, and temporal resolution for smooth motion.

W12. Point: Wearable XR displays require 7 to 8 times higher ppi than the 326 ppi standard for distant displays.

## Unit U17: open question

### Set X

X1. Question: Compare the optical path of the human eye to that of an engineered lens system in a VR headset. What specific differences in media and refractive indices exist between the two?
   Reference answer: In the human eye, light travels through five different media before hitting the retina: air, the cornea, aqueous fluid, the natural lens, and the vitreous fluid, each with distinct refractive indices. In contrast, an engineered lens setup (like a VR headset) typically involves light passing from a screen through a convex lens and then through air. The engineered system is designed to supplement the eye's natural operation by creating a virtual image that eventually projects a real image onto the retina.

X2. Question: How does binocular vision facilitate stereoscopic perception, and what is the significance of the common region shared by both eyes?
   Reference answer: Binocular vision allows both eyes to see the same area over an angle of about 120 degrees when focusing on infinity. Stereoscopy utilizes this by providing two slightly different 2D images to each eye simultaneously. Because the brain processes these two images together, it generates a 3D view of the objects, which enhances depth perception and helps the user understand the spatial relationships between objects in a 3D environment.

X3. Question: Describe the six degrees of freedom (6DoF) in 3D space and explain why they are critical for motion perception in XR systems.
   Reference answer: The six degrees of freedom consist of three rotational movements—yaw, pitch, and roll—and three translational movements along the x, y, and z axes. These are critical because the human brain perceives movement based on these specific types of motion. To create a convincing immersive experience, the engineered system must support these degrees of freedom accurately to 'fool' the user's natural perception of movement within a virtual world.

X4. Question: Why is the traditional 'Retina Display' standard (326 ppi) insufficient for VR headsets, and what technical strategies can be used to address resulting visual artifacts?
   Reference answer: The Retina Display standard is suitable for devices viewed from a distance (like smartphones or laptops), but VR headsets place the display very close to the eye, requiring a pixel density 7 to 8 times higher than 326 ppi. To mitigate visual artifacts like aliasing (jagged lines) and the screen door effect, designers can increase spatial resolution, adjust the field of view, or use techniques like foveated rendering.

### Set Y

Y1. Question: How does placing a screen in a virtual reality headset at the focal length of its engineered lens allow the screen to appear distant while still enabling perception on the retina?
   Reference answer: It makes the close screen appear as an enormous virtual image at an infinite distance. The headset's convex lens focuses the screen's light on the retina, forming a real image. A real image on the retina is required for perception.

Y2. Question: Why is the 326 pixels per linear inch retina display criterion suitable for distant augmented reality displays but not very suitable for head-mounted displays, virtual reality headsets, or wearable displays?
   Reference answer: The 326 pixels per linear inch criterion can be considered for augmented reality displays at a distance, such as televisions, laptops, and smartphones. For head-mounted displays, virtual reality headsets, or wearable displays close to the eye, a magnifying lens brings the display close to the eye. Therefore, the required pixels per linear inch is probably 7 to 8 times higher than a retina display.

Y3. Question: How does binocular vision enable stereoscopy to produce a three-dimensional view from left and right two-dimensional images?
   Reference answer: Binocular vision gives both eyes a common region of about 120 degrees when they focus on infinity. Stereoscopy then uses the left eye to process the left two-dimensional image and the right eye to process the right one. Processing these images simultaneously generates a three-dimensional view, and binocular vision enhances depth perception of object relationships in three-dimensional space.

Y4. Question: Why must a virtual reality headset have a temporal resolution higher than ordinary television or movie frame rates for motion perception?
   Reference answer: It must allow motion to be perceived smoothly without jitter. Temporal resolution is the frame rate, that is, the speed at which display pixels change, and in an immersive environment a virtual reality headset requires frame rates much higher than ordinary television or movie standards such as 24 or 60 frames per second. Higher frame rates are preferred.

### Set Z

Z1. Question: How does the physical arrangement of a virtual reality headset allow the user to perceive a virtual image at an infinite distance?
   Reference answer: A virtual reality headset places a screen very close to the eyes and uses a convex lens to focus the screen's light on the retina. The screen is placed at the focal length of its engineered lens so that it appears to the user as an enormous virtual image at an infinite distance.

Z2. Question: Why is the retina display criterion not suitable for designing virtual reality headsets or wearable displays?
   Reference answer: The 326 pixels per linear inch (ppi) retina display criterion is suitable for distant displays such as televisions, laptops, and smartphones. For head-mounted displays or wearable displays close to the eye, a magnifying lens brings the display close, requiring the pixels per linear inch to be probably 7 to 8 times higher than a retina display.

Z3. Question: How does stereoscopic vision, aided by binocular vision, enable a person to perceive three-dimensional objects?
   Reference answer: Stereoscopic vision is the process in which two eyes view two two-dimensional images simultaneously, generating a three-dimensional view of the objects. This process is aided by binocular vision, which enhances depth perception and helps a person understand the relationship between objects in three-dimensional space.

### Set W

W1. Question: How do the refractive media and the final image surface differ between the human eye and an engineered lens setup?
   Reference answer: Light passes through five different media with unique refractive indices in the human eye, whereas it typically passes through air in an engineered lens setup. Additionally, the human eye has a non-planar retina as an image surface, while an engineered setup uses a focal plane.

W2. Question: Why is the combined optical power of the cornea and natural lens sufficient to focus images of faraway objects?
   Reference answer: Focusing parallel rays onto the retina center requires a lens of at least 40 diopters. Because the cornea provides approximately 40 diopters and the natural lens provides approximately 20 diopters, their combined power of 60 diopters is sufficient to focus images.

W3. Question: Why does a VR headset require a much higher pixel density than a standard retina display?
   Reference answer: A retina display is suitable for devices at a distance like TVs or smartphones. Because VR headsets bring the display very close to the eye using a lens for magnification, the required pixel density must be 7 to 8 times higher than a traditional retina display.

W4. Question: How does the common region in binocular vision facilitate stereoscopy?
   Reference answer: Binocular vision provides a common 120-degree region where both eyes see the same image. When two 2D images, each for one eye, are processed simultaneously, this setup generates a 3D view of the objects, a concept known as stereoscopy.

## Unit U18: odd one out

### Set X

X1. Items: Yaw | Pitch | Roll | X-axis
   Marked odd: X-axis
   Reason: Yaw, pitch, and roll are the three rotational degrees of freedom, whereas the x-axis is one of the translational degrees of freedom.

X2. Items: Spatial Resolution | Intensity Resolution | Temporal Resolution | Refractive Index
   Marked odd: Refractive Index
   Reason: Spatial, intensity, and temporal resolutions are listed as the three important considerations for designing display hardware, whereas refractive index describes the optical properties of the media through which light passes in the eye.

### Set Y

Y1. Items: Yaw | X-axis | Pitch | Roll
   Marked odd: X-axis
   Reason: Yaw, roll, and pitch are rotational degrees of freedom; the x-axis is a translational degree of freedom.

Y2. Items: Refractive index | Temporal resolution | Intensity resolution | Spatial resolution
   Marked odd: Refractive index
   Reason: Spatial resolution, intensity resolution, and temporal resolution are types of display resolution; refractive index is a property of the media through which light passes.

### Set Z

Z1. Items: Vitreous fluid | Cornea | Retina | Aqueous fluid
   Marked odd: Retina
   Reason: Cornea, aqueous fluid, and vitreous fluid are media through which light passes in the human eye before the retina; the retina is the image surface where light is converted into neural signals.

Z2. Items: Spatial resolution | Temporal resolution | Intensity range | Field of view
   Marked odd: Field of view
   Reason: Spatial resolution, intensity range, and temporal resolution are display properties needed to match human visual performance; field of view is the angular region visible to the eye.

### Set W

W1. Items: Roll | Yaw | X axis | Pitch
   Marked odd: X axis
   Reason: Yaw, roll, and pitch are rotational degrees of freedom; the x axis is a translational degree of freedom.

## Unit U19: put in order

### Set X

X1. Title: Order the media a light ray passes through before it reaches the retina
   1. Passes through the air
   2. Passes through the cornea
   3. Passes through the aqueous fluid
   4. Passes through the natural lens
   5. Passes through the vitreous fluid

### Set Y

Y1. Title: Order the media a ray of light passes through in the human eye
   1. The ray of light passes through air with a refractive index of 1.009
   2. The ray of light passes through the cornea with a refractive index of 1.376
   3. The ray of light passes through the aqueous fluid with a refractive index of 1.336
   4. The ray of light passes through the natural lens with a refractive index of 1.413
   5. The ray of light passes through the vitreous fluid with a refractive index of 1.337

### Set Z

Z1. Title: Order the path of light as it enters the human eye
   1. Light travels through the air.
   2. Light passes through the cornea.
   3. Light passes through the aqueous fluid.
   4. Light passes through the natural lens.
   5. Light passes through the vitreous fluid.
   6. Light hits the retina.

### Set W

W1. Title: Path of light through the human eye
   1. Light enters from the air
   2. Light passes through the cornea
   3. Light travels through the aqueous fluid
   4. Light passes through the natural lens
   5. Light travels through the vitreous fluid
   6. Light hits the retina

## Unit U20: concept map

### Set X

X1. cornea --acts as a powerful--> lens

X2. photoreceptor --converts light into--> neural signal

X3. neural signal --is transmitted to the brain through--> optic nerve

X4. human eye --has no--> focal plane

X5. virtual reality headset --has its screen placed at the focal length of its--> engineered lens

X6. left eye --in binocular vision sees the same image over the common region of about 120 degrees as the--> right eye

X7. left eye --in stereoscopy processes the left--> two-dimensional image

X8. stereoscopic vision --helps a person perceive--> three-dimensional object

X9. motion --is perceived in--> virtual environment

X10. motion --is perceived in a virtual world with respect to the supported--> degree of freedom

X11. temporal resolution --must allow motion to be perceived smoothly without--> jitter

X12. retina display criterion --is not very suitable for a--> wearable display

### Set Y

Y1. Human Eye --is part of--> Cornea

Y2. Human Eye --is part of--> Natural Lens

Y3. Human Eye --is part of--> Retina

Y4. Engineered Lens Setup --is used in--> VR Headset

Y5. VR Headset --contains--> Screen

Y6. Convex Lens --is a type of--> Engineered Lens Setup

Y7. Field of View (FOV) --is a property of--> Human Eye

Y8. Binocular Vision --enhances--> Depth Perception

Y9. Stereoscopy --helps perceive--> Depth Perception

Y10. Spatial Resolution --causes--> Aliasing

Y11. VR Headset --requires high--> Spatial Resolution

Y12. VR Headset --requires high--> Temporal Resolution (Frame Rate)

### Set Z

Z1. Visual Perception & XR Displays --guides design of--> Engineered Display Systems

Z2. Human Eye Anatomy --contains--> Cornea (40 Diopters)

Z3. Human Eye Anatomy --contains--> Lens (20 Diopters)

Z4. Human Eye Anatomy --contains--> Retina

Z5. Human Eye Anatomy --light passes through--> Optical Path (5 Media)

Z6. Human Vision Physiology --defines--> Binocular Vision

Z7. Binocular Vision --enables--> Stereoscopy

Z8. VR Headset --uses--> Convex Lens

Z9. Spatial Resolution --causes--> Aliasing

Z10. Spatial Resolution --causes--> Screen Door Effect

Z11. Temporal Resolution --measured by--> Frame Rate

Z12. Engineering Design Requirements --consists of--> Intensity Resolution

## Unit U21: recall

### Set X

X1. Prompt: What is Visual Perception?
   Answer: The biological and neurological process by which our eyes capture light and our brain interprets it to perceive colors, depth, and scenes.
   Taught in: lecture 27 (Visual Perception & Displays I)

X2. Prompt: What is VR Hardware?
   Answer: The physical components of a virtual reality system, such as headsets containing screens and convex lenses, used to create immersive environments.
   Taught in: lecture 13 (VR Hardware)

X3. Prompt: What is AR Hardware?
   Answer: The physical devices used in augmented reality to overlay digital information onto the real world, such as smart glasses or mobile screens.
   Taught in: lecture 15 (AR Hardware)

X4. Prompt: What is Tracking?
   Answer: The process of monitoring and recording the position and orientation of a user or object in a 3D environment.
   Taught in: lecture 16 (Understanding Tracking I)

X5. Prompt: What are Human Factors?
   Answer: The study of human-centric requirements, including physical and perceptual limitations, to design systems that adequately fool our senses and remain usable.
   Taught in: lecture 25 (Human Factors in XR)

X6. Prompt: What are Degrees of Freedom?
   Answer: The independent ways an object can move in 3D space, categorized into 3 rotational (yaw, roll, pitch) and 3 translational (x, y, z) movements.
   Taught in: lecture 16 (Understanding Tracking I)

### Set Y

Y1. Prompt: What is photoreceptor?
   Answer: Photoreceptor is a bodily sensor in the eye's retina that is activated only by visible light and converts visible light into neural pulses for visual perception.
   Taught in: lecture 25 (Human Factors in XR)

Y2. Prompt: What is virtual reality headset (VR)?
   Answer: Virtual reality headset is a wearable display that places a screen close to the eyes and uses a lens to focus the screen's light on the retina, making the screen appear as a virtual image.
   Taught in: lecture 27 (Visual Perception & Displays I)

Y3. Prompt: What is human eye?
   Answer: The human eye is the sense organ for vision that contains a cornea, iris, pupil, and natural lens and focuses visible light on the retina, where photoreceptors convert it into neural pulses sent to the brain.
   Taught in: lecture 27 (Visual Perception & Displays I)

Y4. Prompt: What is retina?
   Answer: Retina is the non-planar image surface at the back of the eye where light falls and is converted by photoreceptors into neural pulses transmitted to the brain by optic nerve fibers.
   Taught in: lecture 27 (Visual Perception & Displays I)

Y5. Prompt: What is lens?
   Answer: A lens is an engineered part of a virtual reality headset or a natural part of the human eye that guides and refracts light so that images are focused on the retina.
   Taught in: lecture 27 (Visual Perception & Displays I)

Y6. Prompt: What is cornea?
   Answer: The cornea is a refracting medium in the human eye that acts as a powerful lens with fixed focal depth, helping focus incoming light onto the retina.
   Taught in: lecture 27 (Visual Perception & Displays I)

### Set Z

Z1. Prompt: What is the physiology of vision?
   Answer: The biological process by which light enters the eye, is focused by the cornea and lens onto the retina, and is converted into neural signals by photoreceptors.
   Taught in: lecture 27 (Visual Perception & Displays I)

Z2. Prompt: What is a VR headset?
   Answer: A wearable display device that provides an immersive experience by obscuring the physical world and rendering a virtual environment.
   Taught in: lecture 13 (VR Hardware)

Z3. Prompt: What is AR hardware?
   Answer: Physical devices, such as smart glasses or head-mounted displays, designed to overlay digital content onto the real world.
   Taught in: lecture 15 (AR Hardware)

Z4. Prompt: What are human factors in XR?
   Answer: The study of human physical and cognitive capabilities and limitations when interacting with virtual and augmented reality systems.
   Taught in: lecture 25 (Human Factors in XR)

Z5. Prompt: What is cybersickness?
   Answer: A form of motion sickness caused by a sensory mismatch between the visual input and the vestibular system in a virtual environment.
   Taught in: lecture 10 (Cybersickness)

Z6. Prompt: What are the degrees of freedom in 3D space?
   Answer: The six independent ways an object can move: 3 rotational axes (yaw, pitch, roll) and 3 translational axes (x, y, z).
   Taught in: lecture 16 (Understanding Tracking I)
