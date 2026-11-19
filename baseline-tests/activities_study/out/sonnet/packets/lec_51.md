# Lecture 51: VR experience optimisation

Transcript: transcripts/lec_51.txt

Goal: Explain how to convert a minimum-time all-POI VR tour into a time-weighted travelling-salesman problem and recover a valid path that limits exposure duration to reduce cybersickness.

Objectives:
- Describe how cybersickness-related exposure-duration limits in semi-interactive VR tours lead to POI path-optimization problems.
- Model the minimum-time all-POI VR tour as a weighted graph whose edge weights are travel times estimated by the natural walking-speed model.
- Transform the minimum-time POI tour into a complete time-weighted travelling-salesman problem and describe how to recover a valid original-graph path while respecting a cybersickness time threshold.

Earlier lectures: 1: General Intro to XR; 2: Application Domains and System Categories; 3: Application Domains and System Categories; 4: Definitions; 5: Definitions; 6: Historical Evolution; 7: Historial Evolution; 8: Issues & Challenges; 9: Issues & Challenges; 10: Cybersickness; 11: Cybersickness; 12: Cybersickness; 13: VR Hardware; 14: VR Hardware; 15: AR Hardware; 16: Understanding Tracking I; 17: Understanding Tracking - I; 18: Understanding Tracking II; 19: VR Software; 20: VR Software; 21: AR Software; 22: AR Software; 23: XR as Interactive Systems; 24: XR as Interactive Systems; 25: Human Factors in XR; 26: Human Factors in XR; 27: Visual Perception & Displays I; 28: Visual Perception & Displays II; 29: Auditory Sense & Immersive Experience; 30: Auditory Sense & Immersive Experience; 31: Other Senses & Full Immersion; 32: Interactive System Development Life Cycle Stages; 33: Introduction to Majuli case study; 34: Introduction to Majuli case study; 35: Usability requirement gathering and specification; 36: Usability requirement gathering and specification; 37: Usability requirement gathering and specification; 38: System Design; 39: System Design; 40: System Design; 41: System Design; 42: System Implementation; 43: System Implementation; 44: System Implementation; 45: System Implementation; 46: System Implementation; 47: System Implementation; 48: System Implementation; 49: VR experience optimisation; 50: VR experience optimisation

## Unit U29: quiz

### Set X

X1. What is the primary objective of the optimization approach discussed in this lecture?
   A. To increase the realism of the virtual world
   B. To minimize the duration of exposure in a virtual world to reduce cybersickness
   C. To increase the visual speed of the optic flow
   D. To create a more complex mental map for users
   Marked correct: B
   Explanation: The lecture explicitly states that the objective is to optimize for cybersickness by controlling the exposure duration, as cybersickness symptoms rise proportionally with the duration of exposure.

X2. According to the lecture, how is cybersickness correlated with VR session duration?
   A. It is inversely proportional
   B. It is unrelated to duration
   C. The more the duration, the more severe the symptoms will be
   D. It only occurs after a specific minimum duration
   Marked correct: C
   Explanation: The speaker notes that the degree of cybersickness symptoms rises proportionally with the VR session duration, meaning shorter duration can help minimize the onset of sickness.

X3. Why is simply increasing the navigation speed not always the best way to reduce exposure time?
   A. It increases the complexity of the graph
   B. It does not provide a natural walking experience
   C. It makes the virtual world too small
   D. It automatically removes all points of interest
   Marked correct: B
   Explanation: While higher speed reduces travel time, the speaker explains that for a realistic walking experience, we cannot modify the speed arbitrarily because we look for 'naturalness' in movement.

X4. How is the virtual world represented in the graph theoretic formulation?
   A. As a set of edges only
   B. As a weighted graph G(V, E)
   C. As a complete graph where every node is connected
   D. As a sequence of points
   Marked correct: B
   Explanation: The problem is formulated using a weighted graph G(V, E), where V represents the set of vertices (POIs) and E is the set of weighted edges.

X5. What weight is assigned to pairs of vertices that are not directly connected in the original graph G?
   A. Zero
   B. The shortest path distance
   C. A very large number (infinity)
   D. The average travel time
   Marked correct: C
   Explanation: If two vertices are not directly connected, the weight is assigned a very large number denoted by the infinity symbol.

X6. How is the weight of a hypothetical edge in the complete graph G' determined?
   A. By assigning it a weight of infinity
   B. By setting it to the Euclidean distance of the two points
   C. By identifying the shortest path between the two vertices in the original graph G
   D. By averaging the weights of all other edges
   Marked correct: C
   Explanation: For vertices not directly connected, the weight of the hypothetical edge is the shortest path length between those vertices in the original graph.

X7. What is the final conversion made to the edge weights in the graph before passing it to the TSP solver?
   A. Converting distances to Euclidean coordinates
   B. Converting distances to travel time based on the natural walking model
   C. Converting weights to infinity
   D. Converting weights to user interaction time
   Marked correct: B
   Explanation: After converting the graph to a complete graph, the weights are replaced with the travel time between the pair of vertices.

X8. What is the 'natural walking model' used to calculate?
   A. The size of the virtual world
   B. The total travel time between two connected nodes
   C. The weight of the vertices
   D. The level of cyber sickness
   Marked correct: B
   Explanation: The natural walking model is used to compute the total travel time between two directly connected vertices with natural walking speed.

X9. In the travel time formula, what does $V_{perceived}$ represent?
   A. The actual speed of the user
   B. The rate at which the scene changes (optic flow)
   C. The vertex count
   D. The height of the user
   Marked correct: B
   Explanation: The speaker mentions that the model provides a visual speed, or the optic flow, which is the rate at which the scenes change in the virtual world.

X10. How does the travel time $	au_D$ depend on the user's physical characteristics?
   A. It only depends on the distance D
   B. It depends on the user's height (h)
   C. It is independent of the user
   D. It depends only on the step frequency
   Marked correct: B
   Explanation: The formula for $V_{act}$ and subsequent $V_0$ depends on the height (h) of the user.

X11. In the algorithm, what is the input and the output?
   A. Input: Time limit; Output: Path; Input: Graph G; Output: Optimal time T and path P
   B. Input: Graph G; Output: Time limit
   C. Input: Path P; Output: Graph G
   D. Input: Cyber sickness level; Output: Optimal speed
   Marked correct: A
   Explanation: The lecturer says: 'here our input is the original graph G... and the output is the optimal time T and path P.'

X12. Why might the minimum time found by the first approach still be a problem?
   A. It might be too fast for the user to perceive
   B. It might still exceed the cyber sickness time threshold if the terrain is very large
   C. It doesn't include all points of interest
   D. It makes the optic flow zero
   Marked correct: B
   Explanation: The speaker notes that even the minimum time for a large terrain might still cross the threshold beyond which cyber sickness may happen, requiring the second approach (fixed time limit).

### Set Y

Y1. Which aspect is not part of the natural walking model's role in a system-controlled virtual tour?
   A. experience optimization
   B. realistic walking feel
   C. scene-change matching
   D. presence enhancement
   Marked correct: A
   Explanation: The natural walking model's role is to support presence through realistic movement, not to optimize the experience. Presence, realistic feel, and scene-change matching are part of that role.

Y2. In a VR navigation optimization approach based on the natural walking model, what is controlled to address cybersickness?
   A. the interaction time at each point of interest
   B. the duration of exposure in the virtual world
   C. the number of points of interest visited
   D. the travel speed between points of interest
   Marked correct: B
   Explanation: The optimization approach addresses cybersickness by controlling how long the user is exposed to the virtual world. Travel speed, POI count, and interaction time may influence exposure, but they are not the target named by this approach.

Y3. In the graph model of a virtual world, what condition leads to an infinite edge weight for a pair of POIs?
   A. A high walking speed is assumed for the pair
   B. A large Euclidean distance is recorded for the pair
   C. A direct path is absent for the pair
   D. A long interaction period is planned for the pair
   Marked correct: C
   Explanation: Edge weights are finite Euclidean distances when two POIs are directly connected and are set to infinity when they are not directly connected. A large distance, an assumed speed, or a planned interaction period does not by itself make the edge weight infinite.

Y4. What does the optimum all-POI tour path need to achieve?
   A. It uses every edge in the graph at realistic speed
   B. It finishes in the least possible time at realistic speed
   C. It finishes after a fixed exposure limit at realistic speed
   D. It visits a subset of POIs at realistic speed
   Marked correct: B
   Explanation: The optimum tour is a path that covers all POIs and finishes in the least possible time while maintaining a realistic speed. It is not defined by a fixed exposure limit, using every edge, or visiting only a subset of POIs.

Y5. How is a small time element for a distance element obtained in the travel-time derivation?
   A. Divide the distance element by the perceived instantaneous walking speed
   B. Multiply the distance element by the perceived instantaneous walking speed
   C. Divide the distance element by the actual instantaneous realistic walking speed
   D. Take the inverse of the distance element divided by the perceived instantaneous walking speed
   Marked correct: A
   Explanation: Since speed is distance over time, a distance element divided by the perceived speed gives the corresponding time element. Using the actual speed instead would omit the visual-gain scaling.

Y6. What determines the constant V naught in the travel-time estimate for a particular user?
   A. The user's height
   B. The user's step frequency
   C. The user's visual gain
   D. The user's walking distance
   Marked correct: A
   Explanation: V naught is specified as a constant for a given user height, while step frequency, visual gain, and walking distance do not determine it in the model.

Y7. What weight is assigned to a hypothetical edge between two vertices that are not directly connected?
   A. the Euclidean distance between them in the original graph
   B. the length of the shortest path between them in the original graph
   C. the average length of all routes between them in the original graph
   D. the length of the longest path between them in the original graph
   Marked correct: B
   Explanation: For pairs without a direct connection, the hypothetical edge is weighted by the shortest existing path between them in the original graph. The Euclidean distance is used only when the vertices are directly connected.

Y8. In a standard TSP instance, what must the path do?
   A. visit each node at least twice and return to the starting node
   B. visit each edge exactly once and return to the starting node
   C. visit each node exactly once and stop at the final node
   D. visit each node exactly once and return to the starting node
   Marked correct: D
   Explanation: The travelling salesman problem requires a cycle through each node exactly once, ending back at the start. Visiting nodes at least twice, covering edges exactly once, or stopping at the final node describes a different routing requirement.

Y9. What measure is recorded for a hypothetical edge between two unconnected vertices in the points-of-interest graph?
   A. The hop count between those vertices in the original graph
   B. The shortest-path distance between those vertices in the original graph
   C. The travel time between those vertices in the original graph
   D. The Euclidean distance between those vertices in the original graph
   Marked correct: B
   Explanation: A missing pair of vertices is joined by a hypothetical edge whose value is based on the shortest route between them in the original graph. Euclidean distance is the original direct-edge weight, and travel time is used only after the completed graph is reweighted.

Y10. After the points-of-interest graph has been completed, what do the edge weights given to the travelling-salesman solver represent?
   A. The shortest path lengths between each pair of vertices
   B. The travel times between each pair of vertices
   C. The Euclidean distances between each pair of vertices
   D. The number of intermediate vertices between each pair of vertices
   Marked correct: B
   Explanation: The completed graph is reweighted so that each edge weight is the travel time between the two vertices, not the Euclidean distance or the raw shortest-path length. The TSP solver therefore optimizes total travel time.

Y11. What must be done to an edge of the TSP solution whose endpoints are not directly connected in the original graph?
   A. It is kept and its endpoints are treated as directly connected in the original graph
   B. It is removed and its endpoints are joined by a direct edge in the original graph
   C. It is replaced by the shortest path between its endpoints in the original graph
   D. It is replaced by the longest path between its endpoints in the original graph
   Marked correct: C
   Explanation: The TSP solution may use hypothetical edges that do not exist in the original graph, so each such edge is expanded into the shortest original path between its endpoints. Removing it or keeping it would not restore a valid original-graph path.

Y12. In the VR path-planning methods, what does the time-limited approach aim to accomplish?
   A. Replacing Euclidean distances with walking-speed-based travel times for every pair of vertices
   B. Visiting the largest set of points of interest within the allowed duration
   C. Removing each hypothetical edge from the solver's output before presenting the final route
   D. Visiting every point of interest in the shortest possible total travel time
   Marked correct: B
   Explanation: The time-limited approach changes the objective from covering every point of interest to visiting as many as possible before the duration runs out; the other options describe steps of the minimum-time method rather than the goal of the time-limited one.

### Set Z

Z1. What is a potential drawback of adjusting the distances between points of interest or altering the virtual terrain?
   A. it prevents users from perceiving the true size of the space and hampers wayfinding
   B. it reduces the travel speed to a point where the experience is no longer realistic
   C. it forces the system to ignore the interaction time at each point of interest
   D. it increases the interaction time required to manipulate virtual objects
   Marked correct: A
   Explanation: While manipulating terrain or POI distances can reduce travel time, these arbitrary changes can prevent users from perceiving the true size of the space and hamper their mental map and wayfinding.

Z2. What is the expected outcome of optimizing the duration of exposure in a virtual reality tour?
   A. it reduces the geographical area the user needs to cover in the virtual space
   B. it ensures the user navigates the virtual world at a natural walking speed
   C. it is expected to optimize the prevalence and onset of cybersickness
   D. it allows for the use of teleportation-type movement between points
   Marked correct: C
   Explanation: Because exposure duration and cybersickness are directly related, optimizing the duration of exposure is expected to optimize (reduce) the prevalence and onset of cybersickness.

Z3. How is the virtual world represented as a weighted graph?
   A. As a set of vertices representing sensory stimuli and edges representing interaction times
   B. As a set of vertices representing physical structures and edges representing scene boundaries
   C. As a set of vertices representing points of interest and edges representing top-view paths
   D. As a set of vertices representing the user path and edges representing navigation times
   Marked correct: C
   Explanation: The virtual world is represented as a graph where the vertices are points of interest and the weighted edges represent a top-view of the world.

Z4. What is the relationship between objects in the virtual world and nodes in the graph?
   A. Each object may contain multiple points of interest, which are the nodes
   B. Each object is represented as a single node regardless of its content
   C. Each node in the graph represents a unique and exclusive physical object
   D. Each point of interest corresponds to a single object in the virtual world
   Marked correct: A
   Explanation: While each POI is a node, an object or structure is not necessarily a single node because it may contain multiple points of interest.

Z5. In the natural walking-speed model, how is the perceived instantaneous walking speed derived?
   A. By multiplying the actual instantaneous realistic walking speed by 2.1
   B. By adding the instantaneous step frequency to the actual realistic walking speed
   C. By dividing the actual instantaneous realistic walking speed by 2.1
   D. By multiplying the actual instantaneous realistic walking speed by the user's height
   Marked correct: A
   Explanation: The natural walking-speed model defines the perceived instantaneous walking speed as the visual gain of 2.1 multiplied by the actual instantaneous realistic walking speed.

Z6. What factor determines the value of the constant V naught?
   A. The visual gain of the simulation
   B. The instantaneous step frequency
   C. The height of the user
   D. The distance between nodes
   Marked correct: C
   Explanation: The constant V naught is determined by the user's height h, according to the provided formula.

Z7. How is the travel-time estimate τD for a directly connected vertex pair calculated?
   A. D/V naught multiplied by the product of 3 and a summation term
   B. D/V naught multiplied by the sum of 1/(2k-1)^2 up to n0
   C. The integral of the actual instantaneous realistic walking speed over distance D
   D. D/V naught multiplied by the difference between 3 and a summation term
   Marked correct: D
   Explanation: The travel-time estimate τD is calculated as D/V naught multiplied by the expression (3 - (16/pi^2) * sum_{k=1}^{n0} 1/(2k-1)^2).

Z8. How is the value of a hypothetical edge between two non-connected vertices determined?
   A. the Euclidean distance between the two vertices in the coordinate scene
   B. the product of the importance values of both vertices
   C. the sum of the waiting times of the two vertices
   D. the sum of the edge weights in the shortest path between them
   Marked correct: D
   Explanation: For vertices not directly connected, a hypothetical edge is introduced with a weight equal to the sum of the edge weights in the shortest path between them.

Z9. What characterizes the travel-time minimisation problem in contrast to a standard travelling salesman problem?
   A. it requires the path to return to the starting node
   B. it focuses on maximizing the weight of the edges
   C. it does not assume the graph is complete
   D. it considers vertices with high importance
   Marked correct: C
   Explanation: While the travelling salesman problem assumes a complete graph, the travel-time minimisation problem does not assume the graph is complete, meaning a Hamiltonian path is not guaranteed.

Z10. What step is required after the TSP solver provides an optimal path for the complete time-weighted graph?
   A. The path is simplified by removing any vertices that are not part of the original graph
   B. Hypothetical edges are replaced with shortest paths from the original graph
   C. The path is kept as is since the solver already accounts for the original graph's structure
   D. The path is recalculated using Euclidean distances to ensure the travel time remains constant
   Marked correct: B
   Explanation: Because the TSP solver might use hypothetical edges that do not exist in the original graph, those edges must be replaced by the actual shortest paths in the original graph (Fact 5).

Z11. How are travel times handled between points of interest that are not directly connected in the virtual-world graph?
   A. A hypothetical edge representing the shortest path between them is introduced
   B. A weight based on the natural walking speed of the user is introduced
   C. A weight based on the Euclidean distance between the points is introduced
   D. A weight based on the number of turns between the points is introduced
   Marked correct: A
   Explanation: For non-directly connected vertices, a hypothetical edge representing the shortest path is introduced to compute travel times.

Z12. Why might the minimum-time approach fail to prevent cybersickness?
   A. The travel time may still reach the threshold for cybersickness
   B. The travel time may still meet the threshold for cybersickness
   C. The travel time may still exceed the threshold for cybersickness
   D. The travel time may still fall below the threshold for cybersickness
   Marked correct: C
   Explanation: The minimum-time approach may still result in a travel time that exceeds the cybersickness threshold, which is why a time-limited approach is also used.

### Set W

W1. What is the core assumption for minimizing the onset of cyber sickness?
   A. smaller terrain leads to lower symptoms
   B. shorter exposure duration helps minimize symptoms
   C. longer exposure duration increases symptoms
   D. higher speeds reduce duration of exposure
   Marked correct: B
   Explanation: Shorter exposure duration helps minimize the onset of cyber sickness.

W2. Why is it discouraged to modify the speed of navigation arbitrarily?
   A. it might not feel natural
   B. it might slow down the world
   C. it might crash the system
   D. it might block the mental map
   Marked correct: A
   Explanation: Arbitrary speed imposed on the user may not be a good idea because naturalness is often a goal in VR.

W3. Why is teleportation-type movement not always the preferred choice for minimizing exposure?
   A. it is not compatible with the walking model
   B. it does not represent a natural movement
   C. it causes the most severe cyber sickness
   D. it is impossible to implement in large systems
   Marked correct: B
   Explanation: While teleportation reduces duration, it is not a natural movement and may not be the preferred approach.

W4. What happens to a user's ability to do wayfinding if the terrain shape is arbitrarily changed?
   A. it hampers mental map construction
   B. it makes wayfinding more fluid
   C. it reduces total travel time
   D. it improves navigation ability
   Marked correct: A
   Explanation: Changing the terrain shape arbitrarily prevents the user from getting a true feel of the terrain, which hampers their ability to build a mental map and do wayfinding.

W5. How can interaction time at specific points of interest be optimized?
   A. estimating max interaction time per POI
   B. skipping points of interest automatically
   C. allowing unlimited time at every POI
   D. removing all interaction at POIs
   Marked correct: A
   Explanation: The system can estimate the maximum time an average user requires to interact with a POI and then force the user to move after that.

W6. Why is the problem of finding a minimum duration path covering all POIs mapped to the TSP?
   A. finding the fastest way to reach a single specific node in the graph
   B. finding the shortest path that visits each node exactly once
   C. finding the shortest path to every single node in the graph
   D. finding a path that covers the maximum number of nodes available
   Marked correct: B
   Explanation: The problem of finding a path covering all vertices in minimum time is a variation of the travelling salesman problem (TSP).

W7. What weight is assigned to a hypothetical edge?
   A. the Euclidean distance
   B. the interaction time total
   C. the maximum path distance
   D. the shortest path length
   Marked correct: D
   Explanation: When there is no direct connection, the hypothetical edge weight is the shortest path length between the vertices.

W8. How is the travel time formula derived from the natural walking model?
   A. dividing total distance by nodes
   B. summing Euclidean distances of edges
   C. integrating instantaneous time over distance
   D. multiplying distance by constant speed
   Marked correct: C
   Explanation: To find out the total time, we need to take an integral of dt over a distance d.

W9. What variables are required to determine the actual instantaneous walking speed?
   A. terrain size and interaction time
   B. travel speed and exposure duration
   C. step frequency and user height
   D. visual gain and optic flow
   Marked correct: C
   Explanation: The actual instantaneous walking speed $V_{act}$ can be represented in a form involving $f$ (instantaneous step frequency) and $h$ (height of the user).

W10. Why must the output of the TSP solver be modified before completion?
   A. it may include duplicate points of interest
   B. it may include hypothetical edges not in the original graph
   C. it might not cover every point of interest
   D. it might contain the incorrect total time for the path
   Marked correct: B
   Explanation: The output of the TSP solver will give a path on the graph $G'$ that has hypothetical edges not present in the original graph $G$.

W11. How are hypothetical edges in the optimal path replaced to provide a valid solution?
   A. with a direct Euclidean distance calculation
   B. with a random sequence of points selected from the graph
   C. with a very large numerical value or an infinity symbol
   D. with the actual shortest path from the original graph
   Marked correct: D
   Explanation: We need to replace hypothetical edges in the optimal path with the actual shortest path from the original graph.

W12. How does the size of the virtual world affect the duration of VR exposure?
   A. larger areas require longer exposure
   B. smaller areas require shorter exposure
   C. smaller areas require longer exposure
   D. larger areas require shorter exposure
   Marked correct: A
   Explanation: For large VR systems, it is natural to have longer exposure because the user needs to cover a larger geographical area.

## Unit U30: recap

### Set X

X1. Point: A primary objective of this optimization is to reduce cyber sickness.

X2. Point: Cyber sickness is directly correlated with the duration of exposure in a VR environment.

X3. Point: Exposure duration is influenced by world size, navigation speed, and interaction time.

X4. Point: There is an intimate relationship between travel speed and the total exposure duration.

X5. Point: Arbitrary speed changes can interfere with a user's ability to build an accurate mental map.

X6. Point: In these tours, users only interact with a specific set of Points of Interest (POIs).

X7. Point: The first approach seeks to find a path that covers all POIs in the minimum possible time.

X8. Point: This problem is formulated using graph theory where the virtual world is represented as a graph G.

X9. Point: The goal is to find a path P that includes all vertices in V with the minimum travel time.

X10. Point: Any hypothetical edges in the TSP output path must be replaced with the original shortest paths.

X11. Point: Even an optimal path might exceed safety thresholds in very large environments, requiring further constraints discussed in the next lecture.

X12. Summary text: This lecture explores strategies for optimizing VR navigation to mitigate cyber sickness by minimizing the duration of user exposure to the virtual environment. By modeling the virtual world as a graph where Points of Interest (POIs) are nodes and travel times—derived from a natural walking speed model—are edge weights, the navigation problem is mapped to a Traveling Salesman Problem (TSP). The lecture details an algorithm to find the minimum-time path covering all POIs while maintaining realism, noting that for very large environments, further optimization is needed to limit travel within specific safety thresholds.

### Set Y

Y1. Point: Optimizing the navigation experience in VR addresses cybersickness concerns.

Y2. Point: A system-controlled VR tour model provides a natural walking experience.

Y3. Point: Optimizing cybersickness involves controlling the duration of exposure in the virtual world.

Y4. Point: Cybersickness symptoms rise proportionally with VR session duration.

Y5. Point: Interaction time at points of interest is limited using a priori estimates.

Y6. Point: A second approach is finding an optimum path to experience maximum points of interest within a fixed time.

Y7. Point: Optimizing exposure duration helps reduce the prevalence of cybersickness.

Y8. Point: Edge weights are Euclidean distances between directly connected points of interest.

Y9. Point: Weights are Euclidean distance if connected or infinity if they are not directly connected.

Y10. Point: Total travel time is the integral of instantaneous time over a distance.

Y11. Point: Travel time between vertices is a function of distance and height-dependent constants.

Y12. Point: The final path replaces hypothetical edges with original shortest paths.

### Set Z

Z1. Point: VR navigation speed must be realistic for walking to ensure naturalness rather than being modified arbitrarily.

Z2. Point: Interaction time at each point of interest (POI) in a semi-interactive tour can be limited to an estimate in advance.

Z3. Summary text: The virtual world is represented as a weighted graph where points of interest are nodes and objects may contain multiple nodes. This graph need not be complete, with edge weights representing Euclidean distance or infinity depending on connectivity. The goal is to solve the optimum travel path problem by finding a path covering all points of interest in minimum time while maintaining a realistic speed.

Z4. Point: The first stage of the travel-time algorithm computes the time to travel between two directly connected nodes.

Z5. Point: Perceived instantaneous walking speed is the actual instantaneous realistic walking speed multiplied by a visual gain of 2.1.

Z6. Point: Total travel time over a distance is the integral of the distance element divided by the perceived walking speed.

Z7. Point: The final travel-time estimate τ_D is calculated using the user's height, step frequency, and a Fourier-series expansion.

Z8. Summary text: Travel-time estimates between connected nodes are derived using a natural walking-speed model. Perceived speed is defined as a visual gain multiplied by actual speed to calculate travel time as an integral. This process results in a final travel-time estimate formula based on user height and a Fourier-series expansion.

Z9. Point: The POI graph to complete time-weighted TSP algorithm produces the optimal time and path covering all vertices in G.

Z10. Point: Cybersickness can be minimized by covering all points of interest in minimum time or maximizing points within a time limit.

Z11. Point: The minimum-time approach maps a graph of points of interest to the travelling salesman problem.

Z12. Summary text: Two methods exist for minimizing cybersickness: covering all points of interest in minimum time or maximizing points within a time limit. The minimum-time approach maps points of interest to a graph and uses a walking speed model to solve the travelling salesman problem. Because this approach may still produce travel times that cause cybersickness, it motivates the use of a time-limited optimization approach.

### Set W

W1. Point: For a system-controlled VR tour, the natural walking model creates realistic movement by matching visual speed to perceived walking speed.

W2. Point: The exposure-duration POI path problem minimizes total navigation and interaction time to all POIs or maximizes POIs within fixed time.

W3. Point: The graph need not be complete, because a direct path between two POIs may not exist.

W4. Point: The natural walking-speed model uses f as instantaneous step frequency and h as user height.

W5. Point: The solved estimate τ_D is D/V0 times a Fourier-series factor to n0; V0 is a constant for height h.

W6. Point: The travel-time minimisation problem seeks the minimum total travel time path through all graph vertices, a TSP variation.

W7. Point: The travelling salesman problem seeks the shortest complete-graph path visiting each node once and returning to start.

W8. Point: The added hypothetical edges use shortest-path length, well-defined because the graph is connected; direct edges keep Euclidean distance.

W9. Summary text: Travel-time optimisation is set up as a graph path problem. A path’s travel time is the sum of Euclidean distances between consecutive vertices, and the goal is the minimum-time path through all vertices, a TSP variation. Because TSP assumes a complete graph while the travel-time graph may lack edges, missing pairs receive hypothetical edges weighted by shortest-path lengths. The connectedness of the graph makes those shortest-path lengths well-defined, producing a complete TSP instance.

W10. Point: The POI optimisation algorithm takes original graph G and produces optimal time T and minimum-time path P covering all vertices.

W11. Point: The TSP-based minimum travel time for all POIs can still exceed the cybersickness threshold in large environments.

W12. Point: The minimum-time approach uses a non-complete graph of points of interest, with direct edges weighted by Euclidean distance.

## Unit U31: open question

### Set X

X1. Question: How does optimizing the duration of exposure in a semi-interactive VR tour help reduce cybersickness?
   Reference answer: Optimizing the duration of exposure in a virtual reality tour is expected to optimize the prevalence and onset of cybersickness because exposure duration and cybersickness are directly related. In a semi-interactive virtual tour, shorter exposure duration can help eliminate or at least minimize the onset of cybersickness.

X2. Question: Why does the travel-time minimization algorithm convert the original graph into a complete graph before using a travelling salesman problem solver?
   Reference answer: The algorithm converts the original graph into a complete graph because the travelling salesman problem is posed on a complete graph. The original graph is not assumed to be complete and may contain no Hamiltonian path.

X3. Question: Why must the algorithm post-process the optimal path produced by a travelling salesman problem solver?
   Reference answer: The algorithm must post-process the optimal path because it may contain hypothetical edges that were not in the original graph. The algorithm replaces each edge whose endpoints were not directly connected in the original graph with the shortest path between those endpoints in the original graph to produce the final solution path.

### Set Y

Y1. Question: Why is it necessary to introduce hypothetical edges when formulating the virtual world as a graph for a Traveling Salesman Problem (TSP) solver?
   Reference answer: Realistic environments may not always have a direct path from one place to another, meaning the graph is not complete. Because a standard TSP solver requires a complete graph, hypothetical edges representing the shortest paths between non-directly connected points are introduced.

Y2. Question: How does arbitrarily changing the terrain shape or the size of the virtual world affect the user's ability to perform wayfinding activities?
   Reference answer: Arbitrarily changing the terrain prevents the user from getting a true feel of the terrain and an idea about the size of the real space. This hampers the user's ability to build a mental map, which is required for wayfinding activities.

Y3. Question: Why might the minimum travel time calculated for a tour covering all points of interest still be insufficient for preventing cyber sickness?
   Reference answer: The calculated minimum travel time depends on the size of the virtual environment. If the environment is large, the minimum time required to cover all points of interest may still exceed the threshold beyond which cyber sickness occurs.

Y4. Question: Why must the path output from a TSP solver be modified before it can be used as a final navigation solution?
   Reference answer: The TSP solver produces a path on a modified graph that includes hypothetical edges not present in the original virtual world. These edges must be replaced with the shortest paths from the original graph so the final path corresponds to the actual environment.

### Set Z

Z1. Question: Why can limiting interaction time at each point of interest in a semi-interactive virtual reality tour help reduce cybersickness?
   Reference answer: Cybersickness symptoms rise as virtual reality exposure duration increases. Exposure duration includes time spent inspecting, selecting, or manipulating virtual objects. In a semi-interactive tour, the system can cap interaction at each point of interest by forcing the user to move on after an estimated maximum time, so this capped interaction time can reduce total exposure and thus the risk of cybersickness.

Z2. Question: Why are travel times in the virtual reality tour optimisation computed with the natural walking-speed model instead of assuming an arbitrarily high virtual travel speed?
   Reference answer: The natural walking-speed model displays optic flow that matches the perceived instantaneous walking speed, producing a realistic perception of movement. Although higher virtual travel speed would lower travel time and exposure duration, virtual travel speed cannot be modified arbitrarily when a realistic walking experience is required. Therefore travel-time estimates use the model's constrained realistic speed rather than an arbitrary maximum speed.

Z3. Question: Why must hypothetical edges be added to the original virtual-world graph before it can be solved as a travelling-salesman problem?
   Reference answer: A standard travelling-salesman problem is posed on a complete graph, while the original virtual-world graph need not be complete because some vertex pairs may not be directly connected. For such pairs, the algorithm adds a hypothetical edge whose length is the shortest path between the two vertices in the original graph. This makes the graph complete, so a standard travelling-salesman-problem solver can be used.

Z4. Question: Why may a minimum-time tour that visits every point of interest still be inadequate for reducing cybersickness?
   Reference answer: The minimum-time approach finds the shortest possible tour covering all points of interest, but in a large virtual environment the minimum time may still exceed the time threshold associated with cybersickness. Because cybersickness is correlated with exposure duration, minimizing time alone does not ensure the tour remains under that threshold. An alternative approach can therefore choose the maximum number of points of interest that can be experienced within a given time limit.

### Set W

W1. Question: Why is minimizing the duration of exposure considered a primary method for optimizing the VR navigation experience in this lecture?
   Reference answer: The primary objective is to address and minimize cyber sickness. Because the severity of cyber sickness symptoms is directly correlated with the duration of exposure in a VR environment, reducing the time a user spends navigating helps minimize the onset and severity of these symptoms.

W2. Question: Explain the trade-offs between using a fully automated system, a fully interactive system, and the 'semi-interactive' tour model described by the lecturer.
   Reference answer: In a purely system-automated tool, there is no scope for user interaction, which is not ideal for exploration. A fully interactive system might be complex. The 'semi-interactive' model provides a middle ground: navigation between points is system-controlled (automated), but users are permitted to interact with specific objects at designated Points of Interest (POIs). This allows for a controlled duration while still providing meaningful interaction.

W3. Question: How does the lecturer mathematically bridge the gap between a realistic, non-complete virtual world graph and the standard Traveling Salesman Problem (TSP) solver?
   Reference answer: The lecturer uses a two-step transformation. First, the non-complete graph is turned into a complete graph by adding 'hypothetical edges' between non-connected points, where the weight of the edge is the shortest path distance. Second, the weights of these edges are converted from Euclidean distances to travel times ($\tau_D$) using a natural walking speed model. This allows the use of standard TSP algorithms to find an optimal path.

W4. Question: After obtaining an optimal path from a TSP solver, what final step must be taken before the path can be used in the VR system?
   Reference answer: The output from a TSP solver on a complete graph may include 'hypothetical edges' that do not exist in the original environment. The final step is to identify any such hypothetical edges in the result and replace them with the actual shortest paths from the original graph to ensure the navigation path is physically possible within the virtual world.

## Unit U32: odd one out

### Set X

X1. Items: Navigation | Manipulation | Selection | Inspection
   Marked odd: Navigation
   Reason: Inspection, selection, and manipulation are types of interaction with objects; navigation is a system-controlled process.

### Set Y

Y1. Items: System-controlled VR navigation | Semi-interactive tours with POI interactions | Manual, user-initiated free-roaming navigation | Natural walking speed models
   Marked odd: Manual, user-initiated free-roaming navigation
   Reason: The lecture focuses on system-controlled and semi-interactive tours as the basis for optimizing navigation to reduce cybersickness, whereas manual, user-initiated free-roaming is not a focus of the optimization strategies discussed.

### Set Z

Z1. Items: Teleportation | Interaction time | Virtual world size | Virtual travel speed
   Marked odd: Teleportation
   Reason: Virtual world size, virtual travel speed and interaction time are the factors on which VR exposure duration depends, while teleportation is a virtual locomotion operation rather than one of those exposure-duration factors.

### Set W

W1. Items: Gather requirements | Solve with TSP solver | Convert to complete graph | Replace edge weights
   Marked odd: Gather requirements
   Reason: Convert to complete graph, replace edge weights, and solve with TSP solver are steps of the travel-time minimisation algorithm; gather requirements is a step of the Interactive System Development Life Cycle.

## Unit U33: put in order

### Set X

X1. Title: Order the stages of the algorithm to compute the optimal VR tour path
   1. Convert the original graph to a complete graph by computing and including hypothetical edges.
   2. Update the edge weights in the complete graph to represent travel times instead of distances.
   3. Provide the modified graph to a standard TSP solver to determine an optimal path.
   4. Adjust the resulting path by replacing any hypothetical edges with the corresponding shortest paths.

### Set Y

Y1. Title: Order the stages of the algorithm for mapping a virtual-world graph to a travelling salesman problem instance
   1. Convert the original graph into a complete graph by adding hypothetical edges for non-directly connected pairs of vertices
   2. Replace the Euclidean-distance edge weights with the travel times between each pair of vertices to create a time-weighted graph
   3. Solve the complete time-weighted graph using a standard travelling salesman problem solver
   4. Post-process the optimal path by replacing hypothetical edges with the shortest paths between their respective endpoints

### Set Z

Z1. Title: Order the steps of the minimum-time all-POI tour algorithm
   1. The original POI graph is completed by adding hypothetical shortest-path edges
   2. Euclidean edge weights are replaced by travel times between points of interest
   3. The complete time-weighted graph is solved by a standard travelling salesman problem solver
   4. Hypothetical edges in the optimal solver path are replaced by shortest paths from the original graph

### Set W

W1. Title: Algorithm to find the minimum time travel path covering all points of interest
   1. Represent the virtual world as a graph where vertices are points of interest and edges are weighted by Euclidean distance between directly connected points.
   2. Create a complete graph by introducing hypothetical edges for non-directly connected vertices, using the shortest path length as the edge weight.
   3. Convert these edge weights from distances into travel times using the natural walking speed model.
   4. Input the resulting complete graph into a standard Traveling Salesman Problem (TSP) solver to obtain an optimal time and path.
   5. Identify any hypothetical edges in the solver's output path and replace them with the corresponding shortest paths from the original graph.
   6. Finalize the optimum travel time and the corrected path that corresponds to the actual navigation structure of the virtual environment.

## Unit U34: concept map

### Set X

X1. virtual travel speed --cannot be modified arbitrarily to provide a realistic walking experience in--> virtual environment

X2. semi-interactive virtual tour --after the interaction time at a point of interest expires automatically forces the user to move to another--> point of interest

X3. travel-time estimate --is under--> natural walking speed model

X4. travel-time minimisation problem --aims to minimise--> travel time

X5. shortest path length --is the sum of the--> edge weight

X6. shortest path length --is well-defined because the graph is--> connected

X7. complete time-weighted graph --has edge weights that are not--> euclidean distance

X8. edge weight --before replacement is--> euclidean distance

X9. travelling salesman problem --is mapped from the problem in the--> original graph

X10. complete graph --is given as input to a--> travelling salesman problem solver

X11. optimal path --produced by the travelling salesman problem solver may contain--> hypothetical edge

X12. hypothetical edge --must be removed before--> final solution path

### Set Y

Y1. VR Experience Optimization --addresses--> Cybersickness

Y2. Cybersickness --correlated to--> Exposure Duration

Y3. Exposure Duration --influenced by--> Travel Speed

Y4. VR Experience Optimization --is achieved via--> Optimization Approaches

Y5. Optimization Approaches --is a kind of--> Minimizing Duration to cover all Points of Interest (POIs)

Y6. Optimization Approaches --is a kind of--> Maximizing POIs within a fixed time limit

Y7. Minimizing Duration to cover all Points of Interest (POIs) --formulated as--> Graph Theoretic Formulation

Y8. Graph Theoretic Formulation --edges weighted by--> Euclidean Distance

Y9. Minimizing Duration to cover all Points of Interest (POIs) --calculated using--> Natural Walking Speed Model

Y10. Minimizing Duration to cover all Points of Interest (POIs) --mapped to--> Traveling Salesman Problem (TSP)

Y11. Traveling Salesman Problem (TSP) --solved on--> Complete Graph with Hypothetical Edges

Y12. Optimal Path --is the solution for--> Minimizing Duration to cover all Points of Interest (POIs)

### Set Z

Z1. VR Experience Optimization --aims to minimize--> Cybersickness

Z2. Cybersickness --is correlated with--> Exposure Duration

Z3. Exposure Duration --factor to be controlled--> VR Experience Optimization

Z4. Optimization Strategies --are applied to--> Semi-interactive Tour

Z5. Strategy 1: Minimum Time for All POIs --is a kind of--> Optimization Strategies

Z6. Strategy 2: Maximum POIs for Fixed Time --is a kind of--> Optimization Strategies

Z7. Strategy 1: Minimum Time for All POIs --is solved using--> Graph Formulation

Z8. Graph Formulation --is converted to--> Complete Graph

Z9. Complete Graph --is mapped to--> Traveling Salesman Problem (TSP)

Z10. Travel Time Calculation --defines weights for--> Traveling Salesman Problem (TSP)

Z11. Natural Walking Model --is used for--> Travel Time Calculation

Z12. Travel Time Calculation --defines edge weights for--> Graph Formulation

## Unit U35: recall

### Set X

X1. Prompt: What is cybersickness?
   Answer: A form of motion sickness experienced in VR, which is often correlated with the duration of exposure in the virtual environment.
   Taught in: lecture 10 (Cybersickness)

X2. Prompt: What is optic flow?
   Answer: The visual speed or the rate at which the scene changes in the virtual world, which helps the user perceive movement.
   Taught in: lecture 27 (Visual Perception & Displays I)

X3. Prompt: What is a mental map?
   Answer: An internal representation of the spatial layout of a virtual environment that helps users with wayfinding activities.
   Taught in: lecture 25 (Human Factors in XR)

X4. Prompt: What is wayfinding?
   Answer: The process by which a user navigates through an environment using cues and their internal mental map.
   Taught in: lecture 26 (Human Factors in XR)

X5. Prompt: What characterizes an interactive XR system?
   Answer: A system where users can interact with objects (such as selection, inspection, or manipulation) to receive feedback from the environment.
   Taught in: lecture 23 (XR as Interactive Systems)

X6. Prompt: What is VR software in the context of navigation?
   Answer: The software models and tools used to control navigation, manage user experience, and provide realistic movement models.
   Taught in: lecture 19 (VR Software)

### Set Y

Y1. Prompt: What is cybersickness?
   Answer: A form of motion sickness experienced in VR environments where the severity of symptoms rises proportionally with the duration of exposure.
   Taught in: lecture 10 (Cybersickness)

Y2. Prompt: What is the Majuli Island case study?
   Answer: A case study used to discuss large-scale VR systems and geographical areas to illustrate the scale of virtual worlds.
   Taught in: lecture 33 (Introduction to Majuli case study)

Y3. Prompt: What is optic flow?
   Answer: The rate at which scenes change in the virtual world, which provides the user with the perception of movement.
   Taught in: lecture 27 (Visual Perception & Displays I)

Y4. Prompt: What is the natural walking model?
   Answer: A model used to provide a realistic walking experience by ensuring the perceived instantaneous walking speed matches the visual speed (optic flow).
   Taught in: lecture 48 (System Implementation)

Y5. Prompt: What is wayfinding?
   Answer: The process of navigating through an environment, which depends on the user's ability to build a mental map of the space.
   Taught in: lecture 25 (Human Factors in XR)

Y6. Prompt: What is a semi-interactive tour?
   Answer: A VR tour where navigation is system-controlled, but users are allowed to interact with a specific set of objects at chosen points of interest.
   Taught in: lecture 23 (XR as Interactive Systems)

### Set Z

Z1. Prompt: What is instantaneous step frequency?
   Answer: Instantaneous step frequency is the number of steps per second, where a step is one foot strike to the next foot strike on the ground.
   Taught in: lecture 50 (VR experience optimisation)

Z2. Prompt: What is fourier series?
   Answer: Fourier series is a weighted sum of harmonically related sinusoids that can approximate any continuous periodic function to arbitrary precision, with practical approximations using the first few terms.
   Taught in: lecture 50 (VR experience optimisation)

Z3. Prompt: What is visual gain?
   Answer: Visual gain is a factor in a natural walking speed model that multiplies actual instantaneous walking speed to compute the desired perceived scene-change speed.
   Taught in: lecture 50 (VR experience optimisation)

Z4. Prompt: What is natural walking speed model?
   Answer: Natural walking speed model is a model for a system-controlled virtual reality tour that displays a visual speed, or optic flow, matching the user's perceived instantaneous walking speed by multiplying actual instantaneous walking speed by a visual gain factor, to provide a realistic walking experience.
   Taught in: lecture 50 (VR experience optimisation)

Z5. Prompt: What is virtual reality (VR)?
   Answer: Virtual reality (VR) is an artificial environment experienced through sensory stimuli provided by a computer, in which a person's actions partially determine what happens and which replaces the user's sense of reality without requiring the physical existence of objects or places.
   Taught in: lecture 4 (Definitions)

Z6. Prompt: What is virtual environment?
   Answer: Virtual environment is a non-real, computer-generated graphical representation of a real or imaginary world, populated with artificial objects, that is experienced through computer-generated sensory stimuli.
   Taught in: lecture 4 (Definitions)
