# 2b judge test: lecture 1 (Gemma 4 12B)

48 facts from 2a, 6 segments. Judge seeds [0, 1, 2]; rewrite on seed 0 only. ✓ pass, ✗ fail, – no verdict.

## Failures per run

| Material | seed 0 | seed 1 | seed 2 | failed in all seeds | flips between seeds |
|---|--:|--:|--:|--:|--:|
| evidence | 3 | 4 | 7 | 2 | 7 |
| segment | 7 | 6 | 4 | 3 | 8 |

Majority verdicts (2 of 3 seeds) differ between the materials on 4 facts: 1/S1/F5, 1/S1/F6, 1/S2/F4, 1/S4/F10.

## Rewrites (seed 0)

| Material | kept | rewritten | removed | unresolved | facts after |
|---|--:|--:|--:|--:|--:|
| evidence | 45 | 3 | 0 | 0 | 48 |
| segment | 41 | 5 | 2 | 0 | 48 |

## Every fact

Verdicts: E = evidence only, S = whole segment; one mark per seed. Reasons and outcomes are seed 0's.

### 1/S0: Explain the basic terms of XR and the objectives of the course.

**[1/S0/F0]** Extended reality is a term that is often heard.  
E ✓✓✓ · S ✓✓✓

**[1/S0/F1]** Virtual reality and augmented reality are terms included in the course title.  
E ✓✓✓ · S ✓✓✓

**[1/S0/F2]** Mixed reality is a term that is heard nowadays.  
E ✓✓✓ · S ✓✓✓

**[1/S0/F3]** Finding answers to questions regarding virtual reality, augmented reality, extended reality, and mixed reality is one of the main objectives of the course.  
E ✓✓✓ · S ✓✓✓

### 1/S1: Describe common public perceptions and misconceptions of XR.

**[1/S1/F0]** The terms virtual reality, augmented reality, mixed reality, and extended reality are becoming common, but they can refer to different things for different people.  
E ✓✓✗ · S ✓✗✓

**[1/S1/F1]** To some people, the terms virtual reality, augmented reality, mixed reality, and extended reality immediately bring to mind a magical environment containing imaginary, magical, or unnatural objects.  
E ✓✓✓ · S ✓✓✓

**[1/S1/F2]** Some people perceive 3D or 4D movie theaters showing documentaries on extinct animals as examples of augmented reality and virtual reality.  
E ✓✓✗ · S ✓✓✓

**[1/S1/F3]** The most common public perception of virtual reality is a user wearing a headset and performing actions in a virtual world.  
E ✓✓✓ · S ✓✓✓

**[1/S1/F4]** A headset is worn on the head, blocks vision, and transports the user to a virtual world experienced through the headset.  
E ✓✓✓ · S ✓✓✓

**[1/S1/F5]** Many people perceive augmented reality as viewing the real world on a device screen while seeing virtual objects that do not exist in the real world.  
E ✓✓✓ · S ✗✗✗
- S: This fact fails property 1 (Established) because the lecturer does not assert that 'many' people perceive AR this way; he notes that many have played a specific game and then asks if that is what people think of. It also fails property 7 (Faithful) as it synthesizes descriptions and perceptions rather than staying strictly faithful to the lecturer's phrasing.  
  → removed

**[1/S1/F6]** Some people perceive augmented reality as a way to see things in different ways, such as viewing the internal skeletal structure or the internal vein network of a leg instead of only the skin.  
E ✓✓✗ · S ✗✗✗
- S: This fact fails property 1 (Established) because the lecturer poses this perception as a question in sentence [33] rather than asserting it as a fact. It also fails property 2 (Grounded) as the cited sentences provide an example of a capability rather than an assertion of public perception.  
  → removed

### 1/S2: Define the term Extended Reality (XR) and the concept of immersive technology.

**[1/S2/F0]** Extended reality is an umbrella term.  
E ✓✓✓ · S ✓✓✓

**[1/S2/F1]** Extended reality encapsulates all immersive technologies.  
E ✓✓✓ · S ✓✓✓

**[1/S2/F2]** Augmented reality, virtual reality, and mixed reality are immersive technologies.  
E ✓✓✓ · S ✓✓✓

**[1/S2/F3]** Extended reality is not a reference to a specific technology.  
E ✓✓✓ · S ✓✓✓

**[1/S2/F4]** The variable X in the term extended reality can take any value, and each of those values forms a technology.  
E ✗✗✗ · S ✓✓✓
- E: The fact fails Grounded and Self-contained because 'X' is not a literal part of the term 'extended reality'; the lecturer uses 'X' as a conceptual placeholder to explain the meaning of the word 'Extended'.  
  → rewritten: The term Extended in Extended Reality can be viewed as a variable that can take any value, and each of those values forms a technology.  

**[1/S2/F5]** The variable X in the term extended reality refers to all present or future immersive technologies.  
E ✗✓✓ · S ✓✓✓
- E: The fact fails Grounded and Self-contained because 'X' is not a literal part of the term 'extended reality'; the lecturer uses 'X' as a conceptual placeholder to explain the meaning of the word 'Extended'.  
  → rewritten: The term Extended in Extended Reality refers to all present or future immersive technologies.  

**[1/S2/F6]** Immersive technology is a technology in which a user experiences an environment through sensory organs in such a way that they fail to distinguish that environment from the real environment and perceive the experience as real.  
E ✓✓✓ · S ✓✓✓

### 1/S3: Explain the reality-virtuality continuum.

**[1/S3/F0]** The reality-virtuality continuum is a scale.  
E ✓✓✗ · S ✓✓✓

**[1/S3/F1]** The real environment is at one extreme of the reality-virtuality continuum where nothing is virtual.  
E ✓✓✓ · S ✗✓✓
- S: The fact fails the Grounded property because the term 'reality-virtuality continuum' is not present in the evidence sentence [5], which instead uses the term 'scale'.  
  → rewritten: The real environment is at one extreme of the reality-virtuality continuum scale where nothing is virtual.  

**[1/S3/F2]** The virtual environment is at the other extreme of the reality-virtuality continuum where nothing is real.  
E ✓✓✓ · S ✗✓✓
- S: The fact fails the Grounded property because the term 'reality-virtuality continuum' is not present in the evidence sentences [6, 7, 17].  
  → rewritten: The virtual environment is at the other extreme of the reality-virtuality continuum scale where nothing is real.  

**[1/S3/F3]** The interval between the two extremes of the reality-virtuality continuum contains augmented reality and augmented virtuality.  
E ✓✓✓ · S ✗✓✓
- S: The fact fails the Grounded property because 'the two extremes' and 'reality-virtuality continuum' are not found in the evidence sentence [8].  
  → rewritten: The interval in between the two extremes of the reality-virtuality continuum scale contains augmented reality and augmented virtuality.  

**[1/S3/F4]** Augmented reality is the augmentation of the real world with virtual content.  
E ✓✓✓ · S ✓✓✓

**[1/S3/F5]** Augmented virtuality is the augmentation of the virtual world with real world content.  
E ✓✓✓ · S ✓✓✓

**[1/S3/F6]** The entire space between the virtual environment and the real environment in the reality-virtuality continuum is broadly sometimes referred to as mixed reality.  
E ✓✓✓ · S ✗✓✓
- S: The fact fails the Grounded property because the term 'reality-virtuality continuum' is not found in the evidence sentences [14, 18].  
  → rewritten: The entire space in between the virtual environment and the real environment in the reality-virtuality continuum scale is broadly sometimes referred to as mixed reality.  

### 1/S4: Describe the commercial and social significance of XR and the impact of the Metaverse.

**[1/S4/F0]** In a 2022 forecast, the video game industry is expected to have about 34% content related to extended reality technologies, the healthcare industry about 15% content related to or built on extended reality technologies, engineering 14%, live events 12%, video entertainment 9%, real estate 7%, retail 5%, and military 4%.  
E ✓✓✓ · S ✓✓✓

**[1/S4/F1]** Because military budgets are large, the 4% component of military applications built on extended reality technologies can translate to a huge amount of money.  
E ✓✓✓ · S ✓✓✓

**[1/S4/F2]** There is likely to be a huge commercial interest in extended reality technologies which is likely to grow.  
E ✓✓✓ · S ✓✓✓

**[1/S4/F3]** The market size for extended reality technologies is expected to grow from around 20.5 billion US dollars in 2021 to around 860 billion US dollars by 2030.  
E ✓✓✓ · S ✓✓✓

**[1/S4/F4]** The market size for extended reality technologies is likely to increase exponentially.  
E ✓✓✓ · S ✓✓✓

**[1/S4/F5]** The market for extended reality technologies consists of a hardware market, which is slightly larger at about 60% of the market size, and a software market, which is slightly smaller at about 40%.  
E ✓✓✓ · S ✓✓✓

**[1/S4/F6]** In India, the extended reality industry was estimated to be at around 1.83 billion US dollars in 2020 and is expected to be around 14 billion US dollars in 2027.  
E ✓✓✓ · S ✓✓✓

**[1/S4/F7]** There is significant demand and growth potential for extended reality technology because different applications are going to use it.  
E ✓✓✓ · S ✓✓✓

**[1/S4/F8]** The term metaverse has stimulated and spurred the growth in the field of extended reality heavily.  
E ✓✓✓ · S ✓✓✓

**[1/S4/F9]** The metaverse is an all-around three-dimensional world with a three-dimensional environment where humans will use a natural way of interaction to interact with digital content, reimagining the way humans interact with the digital world.  
E ✓✗✓ · S ✓✗✓

**[1/S4/F10]** Current technology is not yet advanced enough to realize the metaverse, but there is significant scope to improve the technology and companies are investing in that conversion heavily.  
E ✓✗✗ · S ✓✗✓

**[1/S4/F11]** There are technological limitations for the metaverse, but with more investment and research, those will be overcome and growth potential will be there in both hardware and software.  
E ✗✗✗ · S ✗✗✗
- E: The fact fails property 7 (Faithful) because it removes the lecturer's hedge "hopefully" from sentence 54.  
  → rewritten: There are technological bottlenecks and many technological limitations for the metaverse, but hopefully with more investment and research, the technological limitations and bottlenecks will be overcome and the growth potential is going to be huge in both hardware and software.  
- S: The fact fails property 4 (Atomic) as it combines three separate propositions and property 7 (Faithful) because it omits the lecturer's hedge 'hopefully' from sentence 54.  
  → rewritten: There are many technological limitations for the metaverse.  
  → rewritten: With more investment and research, the technological limitations for the metaverse will hopefully be overcome.  
  → rewritten: The growth potential for the metaverse will be in both hardware and software.  

**[1/S4/F12]** The growth of extended reality technologies will result in a need for more knowledgeable and skilled manpower.  
E ✓✓✓ · S ✓✓✓

**[1/S4/F13]** Extended reality is one of the major emerging areas identified by many national governments along with artificial intelligence, large language models, generative artificial intelligence, drones, and nanomaterials.  
E ✓✓✓ · S ✓✓✗

### 1/S5: Summarize the course objectives and the primary case study to be used.

**[1/S5/F0]** Extended reality refers to extending reality by some means intuitively or using systems to augment reality or replace the perception of reality systemically.  
E ✓✓✓ · S ✓✓✓

**[1/S5/F1]** The reality-virtuality continuum consists of one end where reality is completely replaced with virtual reality systems, the other end where virtuality is completely replaced by the entirely real world, and mixed reality or augmented reality concepts in between.  
E ✓✓✓ · S ✓✓✓

**[1/S5/F2]** The reality-virtuality continuum was taken from the 1994 paper "A Taxonomy of Mixed Reality Visual Displays" by Paul Milgram and Fumio Kishino.  
E ✓✓✓ · S ✓✓✓

**[1/S5/F3]** The broad objective of the course is to learn about virtual reality, augmented reality, and allied concepts to master the development and deployment of systems.  
E ✓✓✓ · S ✓✓✓

**[1/S5/F4]** The course covers a basic understanding of all relevant concepts, a theoretical background to build a foundation in the field, and practical knowledge on development and deployment.  
E ✓✓✓ · S ✓✓✓

**[1/S5/F5]** The course uses case studies involving game engines and software development kits to explain how to develop and deploy technologies.  
E ✓✓✓ · S ✓✓✓

**[1/S5/F6]** The course covers how senses influence the use of technology and systems through an understanding of cognitive and psychological aspects.  
E ✓✓✓ · S ✓✓✓

**[1/S5/F7]** The theoretical background of the technology includes building interactive software, building interactive virtual reality or augmented reality systems, software functionality, software components, hardware operation, hardware technologies, and designing and implementing interactions.  
E ✓✓✓ · S ✓✓✓

**[1/S5/F8]** The course uses a case study of a virtual reality system related to a digital heritage preservation project.  
E ✓✓✓ · S ✓✓✓

