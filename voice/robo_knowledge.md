# Robo's facts

Robo answers questions about itself, Texas State University and the Ingram Hall
Makerspace ONLY from this file, so keep it accurate. Edit it freely: plain sentences,
one fact per line. Restart chat.py to load changes.

The whole file goes into every prompt, so keep it focused: chat.py gives the model
room for about 8,000 tokens (num_ctx), and this file should stay under about 5,000
(roughly 20,000 characters).

## About Robo

- Robo is a ROBOTIS OpenMANIPULATOR-X robot arm in the Ingram Hall Makerspace at Texas State University.
- Robo has four joints (base, shoulder, elbow, wrist) and a two-finger gripper. Each joint is a DYNAMIXEL XM430 smart servo motor.
- Robo's brain is an NVIDIA Jetson Orin NX computer running ROS 2 Humble, the Robot Operating System.
- An OpenCR board connects the Jetson to Robo's motors over USB.
- Robo sees with a Logitech BRIO camera and uses YOLO and YOLO-World to recognise people and objects.
- Robo hears with Whisper (speech to text), thinks with a small language model running locally through Ollama, and talks with Piper (text to speech). Everything runs on the Jetson, with no internet needed.
- Robo can wave, nod, shake its head, bow and look around. People can teach Robo new moves by posing its arm and saving each pose.
- Robo greets people automatically when its camera sees someone.
- Robo can be simulated in RViz, a 3D viewer, so new moves can be tested safely before running on the real arm. The simulated arm and the real arm use the same controller.
- Robo's wrist can tilt but not twist, so it picks up objects best when they are placed in a known spot.
- Robo's code is open source on GitHub: aditya-baniya-ai/Open_manipulator_x.

## Texas State University

- Texas State University (TXST) is a public university in San Marcos, Texas, between Austin and San Antonio.
- Texas State students are called Bobcats.
- The Ingram School of Engineering is part of the College of Science and Engineering at Texas State.
- Ingram Hall (Bruce and Gloria Ingram Hall) is a five-floor, 166,851 square foot engineering and science building that opened in fall 2018. It cost 120 million dollars and was the largest building project in Texas State history at the time.
- Ingram Hall is named for Bruce and Gloria Ingram, longtime supporters of the university, who donated toward its construction.
- Ingram Hall is also home to the Keysight Smart Lab, opened in December 2025, where students train on industry-standard electronics test equipment. It is separate from the Makerspace.

## Ingram Hall Makerspace: overview

Sources: engineering.txst.edu/makerspace.html and its pages on access, rates, the
training guide and instructional videos (checked October 2026), plus news articles
named below.

- The Ingram Hall Makerspace (IHM) is the Ingram School of Engineering's fabrication facility. Its motto is "Built by Bobcats, For Bobcats."
- It describes itself as "where imagination meets industrial-grade reality": a hands-on space with the latest manufacturing technology, for prototyping anything from simple concepts to complex engineering systems.
- It is an 11,000 square foot facility. There are other makerspaces on campus, but IHM is built for larger, more precise, harder projects that need more than a desktop 3D printer.
- It is an academic makerspace: the goal is not to turn students into machinists or welders, but into innovative thinkers and creative makers who can safely run real equipment.
- The Makerspace rooms are Ingram Hall 1201, 1202 and 1202A to 1202C. The front desk is in room 1201.
- Hours: Monday to Friday, 8 AM to 5 PM.
- Email: ingrammakerspace@txstate.edu. Questions can also be asked in person in Ingram Hall 1201.
- People walking past can watch the work through the Makerspace's big windows.

## The zones of the Makerspace

- PawPrint Studio: the rapid prototyping zone, with 3D printers, laser cutters and engravers, and electronics workbenches. It is a great place to start.
- Industrial Space: professional-grade CNC machines for high-output, high-precision manufacturing, such as Haas CNC mills and a Haas CNC lathe, manual mills and lathes, and waterjet cutters.
- Welding bay: a dedicated area for structural metal fabrication.
- Woodworking bay: a dedicated area for traditional woodworking.
- Teaching labs attached to the Makerspace include Senior Design Fabrication, CIM and Instrumentation, Composites, and Advanced Additive Manufacturing.
- The Makerspace also has a PCB maker for making circuit boards, and an assortment of hand tools.

## Projects and who uses the Makerspace

- The Makerspace is the main fabrication hub for the student organizations Bobcat Racing, Bobcat Aerospace, and the IEEE Robotics and Automation Society.
- Bobcat Racing is Texas State's Formula SAE team. Students design, build and race a small formula-style race car against university teams from around the world. The team runs like a small car company, with engineering, business and sponsorship roles, so students of any major can help. Contact: bobcatracing@txstate.edu.
- Bobcat Racing was revived in 2021 after COVID, and builds its car in the Makerspace. Research engineer Abhimanyu Sharotry has been its faculty advisor since 2022.
- Bobcat Aerospace is Texas State's first and largest student high-power rocketry club, founded in fall 2021. It builds rockets for competitions like the Spaceport America Cup in New Mexico, where rockets try to fly as close as possible to 10,000 feet, carry a payload and be recovered safely. Any major can join.
- The IEEE Robotics and Automation Society student chapter builds robotics projects in the Makerspace.
- Senior design (capstone) is one of the biggest users: nearly all senior design projects are built, stored and developed in the Makerspace, and successful ones are often displayed near the entrance.
- Classes use it too, for example the CAD/CAM class, where students program CNC mills and then run their own programs on the machines.
- Faculty research projects, and students' personal projects, also use the Makerspace.
- Workshops have been held for new students, where groups make a small custom project with a laser cutter, laser engraver or 3D printer.

## How to get access

- Access is managed through an online system called FOM, at fom.engineering.txstate.edu. FOM is used to sign up, take the policy quiz, track trainings and reserve machines.
- Ingram School of Engineering program directors and staff get badge access directly, with no request needed.
- Everyone else gets access through one of four paths: research, coursework or senior capstone, a student organization, or a personal project.
- Step one for everyone: log in to FOM once with your TXST NetID. Pick the discipline closest to your field. If your supervisor isn't listed, pick "Bobcat, Boko".
- Everyone must sign the Ingram Hall Makerspace Participation Agreement, renewed every academic year (September 1 to August 31).
- Most users also sign a Release of Liability (renewed every year) and a Photograph Release (one time only).
- Then you complete the FOM onboarding: the required forms, the mandatory policy quiz, and linking your student ID card at the front desk kiosk so it opens the doors.
- For a class or senior design team: the instructor requests a course account in FOM with the Course Usage Request or Senior Capstone Request form, then adds students. Students just log in to FOM once and ask their instructor.
- For research: the faculty advisor (the PI) submits a Research Usage Request form, and then adds students and other researchers to the project in FOM.
- For a student organization: an officer or faculty advisor submits a Student Organization Usage Request form. Then the president adds members to the roster in FOM.
- For a personal project: you request your own account with the Personal Project Usage Request form, complete the trainings, and pay for materials and machine time. A faculty or staff mentor signs the form too.
- New accounts usually take about one business day to set up after all forms are signed.
- People must be logged in to FOM at least once before anyone can add them to a course, research project or organization.

## Training before using the machines

- Every machine has its own training requirements. The Makerspace's Equipment Access and Training Guide page has an interactive dashboard and flowcharts that show which trainings each machine needs.
- Safety comes first: users complete a safety certification and the FOM policy quiz before using any equipment.
- Free online courses recommended by the Makerspace include: Additive Manufacturing: Optimizing 3D Prints; Understanding Personal Protective Equipment; Learning Mastercam (CNC programming); and Introduction to Mill and Lathe Operation.
- For the Haas CNC machines, the Makerspace points to the Haas Certification Program, Haas's free online training at learn.haascnc.com.
- Instructional videos on the Makerspace website cover FOM onboarding and 3D printing in the PawPrint Studio.
- If you're not sure what training you need, ask the Makerspace staff at the front desk or email ingrammakerspace@txstate.edu.

## 3D printing in the PawPrint Studio

- 3D printing is one of the easiest ways to start at the Makerspace. It happens in the PawPrint Studio.
- How to start 3D printing: get FOM access, complete the 3D printing safety certification and the FOM quiz, reserve a printer in FOM, log in to the printer with your NetID, upload your G-code file, and then watch your print on the live camera feed.
- G-code is the file of instructions a 3D printer follows. You make it by slicing a 3D model, for example with PrusaSlicer.
- Prusa Core One: an enclosed Prusa 3D printer with a print area of about 25 by 22 by 27 centimeters. The enclosure keeps heat in, which helps with materials like PETG, ASA and ABS. You can buy Makerspace filament for it, or bring your own filament (BYOF).
- Prusa MINI: a small, reliable Prusa printer with a print area of about 18 by 18 by 18 centimeters, good for small parts and first prints.
- Prusa XL: a large Prusa printer with a print area of about 36 by 36 by 36 centimeters. It can have several print heads, so one print can use several colors or materials.
- Markforged Mark Two: an industrial composite 3D printer. It prints a strong nylon-and-carbon material called Onyx, and can lay continuous strands of carbon fiber, Kevlar or fiberglass inside the part, making parts strong enough to replace some aluminum parts. Its print area is about 32 by 13 by 15 centimeters.
- Prints on the Prusa printers use PLA filament from the Makerspace, which costs 2 cents per gram.

## The machines, one by one

These descriptions combine the Makerspace's machine list with the manufacturers'
general specifications. The exact setup of each machine here may differ.

- Haas VF-2: a 3-axis vertical CNC milling machine, an industry-standard machine that cuts parts out of metal or plastic blocks by moving a spinning cutter left-right, forward-back and up-down under computer control. Its working travel is about 30 by 16 by 20 inches.
- Haas VF-3, set up for 5-axis machining: a larger Haas vertical CNC mill. With 5 axes, the part can also tilt and rotate, so complex shapes can be cut from many sides in one setup.
- Haas ST-20Y: a CNC lathe (turning center). It spins the material and cuts round parts like shafts and bushings. Its Y-axis and live tooling also let it drill and mill features off-center, so many parts are finished in one machine.
- Tormach PCNC 440: a compact CNC mill, smaller and easier to learn on than the Haas machines, good for small metal and plastic parts.
- Manual mill and manual lathe: traditional machines that a person controls with hand wheels instead of a computer. They teach the basics of machining and are great for quick, simple parts.
- Shark CNC router: a computer-controlled router for cutting and carving wood, plastic and foam sheets, like signs, panels and furniture parts.
- WardJet waterjet: an industrial waterjet that cuts metal, stone, glass and plastics with a thin stream of extremely high-pressure water mixed with sand-like abrasive. It cuts without heat, so the material doesn't warp.
- Wazer waterjet: a compact desktop waterjet, a smaller and simpler way to cut metal, glass, tile and plastic sheets. Its cutting area is about 12 by 18 inches.
- Torchmate CNC plasma table: cuts steel and other metal sheets with a computer-guided plasma torch. It is fast for making brackets, plates and chassis parts.
- Fiber laser: a laser built for marking and engraving metal, such as serial numbers, logos and labels.
- xTool lasers: desktop laser cutters and engravers, used to cut and engrave wood, acrylic, leather, cardboard and other non-metal materials. They are the easiest lasers to start with.
- Welding bay: welding stations for joining metal parts, used for frames, chassis and other structures. Welding needs special training and protective equipment.
- Woodworking bay: tools for traditional woodworking, like cutting, shaping and sanding wood.
- Electronics workbenches: benches with tools for soldering, building and testing circuits, for robotics and electronics projects.

## How much it costs

Prices from the Makerspace rates page (Spring 2026 rates). They may change, so check
the rates page or ask staff for the latest. "Internal" rates are for class, research,
senior design and student organization work billed to a TXST account. "External" rates
are for everyone else. All rates are per hour, with a 30-minute minimum charge.

- Prusa Core One with Makerspace filament: 1 dollar per hour internal, 1 dollar 50 external. Bring your own filament: 2 dollars internal, 3 dollars external.
- Prusa MINI: 1 dollar per hour internal, 1 dollar 50 external.
- Prusa XL: 2 dollars per hour internal, 3 dollars external.
- Markforged Mark Two: 4 dollars per hour internal, 6 dollars external.
- xTool lasers: 6 dollars per hour internal, 9 dollars external.
- Fiber laser: 24 dollars per hour internal, 36 dollars external.
- Shark CNC router: 15 dollars per hour internal, 22 dollars 50 external.
- Wazer waterjet: 15 dollars per hour internal, 22 dollars 50 external.
- WardJet waterjet: 43 dollars per hour internal, 65 dollars external.
- Torchmate plasma table: 21 dollars per hour internal, 32 dollars external.
- Manual mill: 17 dollars per hour internal, 26 dollars external.
- Manual lathe: 19 dollars per hour internal, 29 dollars external.
- Tormach PCNC 440: 19 dollars per hour internal, 29 dollars external.
- Haas VF-2: 30 dollars per hour internal, 45 dollars external.
- Haas VF-3 (5-axis): 31 dollars per hour internal, 47 dollars external.
- Haas ST-20Y lathe: 32 dollars per hour internal, 48 dollars external.
- Welding bay: 20 dollars per hour internal, 30 dollars external.
- Materials: PLA filament costs 2 cents per gram. Markforged materials are charged by volume: Onyx 25 cents per cubic centimeter, fiberglass 1 dollar 60, Kevlar 2 dollars, high-strength high-temperature fiberglass 2 dollars, and carbon fiber 4 dollars per cubic centimeter.
- Internal on-site use is capped at 450 dollars per month per project, class section, senior design group or research award, not counting materials. Student organizations get one cap per 15 registered members.
- Students doing personal projects pay external rates, unless a faculty member sponsors the project as their mentor, which can qualify them for internal rates.
- The Makerspace has an online e-commerce store for payments, linked from its website.

## People

- The Makerspace has a team of about a dozen staff and student workers. The team is listed on the Makerspace website's "Our Team" page.
- Abhimanyu Sharotry, a research scientist at the Ingram School of Engineering, is on the Makerspace team and studies digital twins and the simulation of manufacturing systems.
- Brian Earle on the Makerspace team is known as "the Haas guy", the go-to person for the Haas CNC machines.

## Tips for visitors

- Ask at the front desk in Ingram Hall 1201 for help with trainings, access or choosing a machine.
- General shop safety: wear safety glasses and closed-toe shoes around machines. The Makerspace's own rules are in its Policies and Procedures, and its training list includes a course on personal protective equipment.
- A great first project is a 3D print or a laser-cut design in the PawPrint Studio.
- The Makerspace accepts donations through the Texas State giving site, to help buy equipment for future engineers.
