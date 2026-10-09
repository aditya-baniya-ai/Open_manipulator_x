# Robo's facts

Robo answers questions about itself, Texas State University and the Ingram Hall
Makerspace ONLY from this file, so keep it accurate. Edit it freely: plain sentences,
one fact per line. Restart chat.py to load changes.

The whole file goes into every prompt, so keep it focused: chat.py gives the model
room for about 12,000 tokens (num_ctx), and this file should stay under about 7,000
(roughly 28,000 characters). If it grows past that, raise num_ctx in chat.py too.

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

Sources: engineering.txst.edu/makerspace.html, its access, rates, training, forms and
documents pages, the Makerspace's Policies and Procedures, New User SOP, 3D printing
SOPs and xTool SOP (2026 versions), Senior Design Day pages, and news articles (checked
October 2026).

- The Ingram Hall Makerspace (IHM) is the Ingram School of Engineering's fabrication facility. Its motto is "Built by Bobcats, For Bobcats."
- It describes itself as "where imagination meets industrial-grade reality": a hands-on space with the latest manufacturing technology, for prototyping anything from simple concepts to complex engineering systems.
- It is an 11,000 square foot facility. There are other makerspaces on campus, but IHM is built for larger, more precise, harder projects that need more than a desktop 3D printer.
- It is an academic makerspace: the goal is not to turn students into machinists or welders, but into innovative thinkers and creative makers who can safely run real equipment.
- Hours: Monday to Friday, 8 AM to 5 PM.
- Email: ingrammakerspace@txstate.edu. In person: Ingram Hall room 1201.
- Everyone enters through the front doors of the PawPrint Studio, at the first floor lobby of Ingram Hall. Entering through side rooms is not allowed.
- The Makerspace staff members are called MSTs. Ask an MST for help with machines, materials or trainings.
- The front desk kiosk is self-service, not staffed. It is where you register your TXST ID card.
- Only TXST students, staff, faculty and authorized guests may enter. A TXST ID card is needed to get in.
- People walking past can watch the work through the Makerspace's big windows.

## The rooms and zones

- PawPrint Studio (Ingram Hall 1201): the rapid prototyping zone and the entrance. It has the 3D printers, the xTool laser cutters and electronics workbenches. It is a great place to start.
- PawPrint Studio has no protective equipment rules, and food and drinks are allowed there as long as they are away from equipment and you clean up.
- Industrial Area (Ingram Hall 1202): professional-grade machines, like the Haas CNC mills and lathe, manual mills and lathes, waterjets and the plasma table.
- Side rooms 1202A to 1202D connect to the Industrial Area. There is also a woodshop and a welding bay.
- Project Work Room (Ingram Hall 1202D): project tables on the right side for short-term project work. The left side is a Mechanical Engineering classroom area. It also has a Kardex vertical lift storage machine, with trays you can rent each month through FOM.
- Teaching labs attached to the Makerspace include Senior Design Fabrication, CIM and Instrumentation, Composites, and Advanced Additive Manufacturing.

## Safety rules

- In the Industrial Area you must wear safety glasses, long pants, a sleeved shirt and closed-toe shoes at all times, even just walking through. No sandals or flip-flops, and shirts may not show shoulders or midriff.
- Bring your own safety glasses. People without the right clothing will be turned away.
- Tie back long hair and loose clothing, and remove jewelry, before running any machine.
- No food or drinks anywhere in the Industrial Area or near machines.
- Never leave a machine running unattended. 3D printers are the only exception.
- Only use machines you are trained and approved for, and follow each machine's Standard Operating Procedure (SOP).
- Check a machine before using it. Report anything broken to staff by email or in FOM, and never bypass safety guards.
- No weapons, or anything that looks like a weapon, may be made in the Makerspace.
- Report every accident or injury to staff, even small ones. For a fire or serious injury, call 911 and tell staff.
- Know where the fire extinguishers, first aid kits, eyewash stations and exits are. One fire extinguisher is at the entrance, between rooms 1201A and 1201B.
- After using a machine: check it back in on FOM, turn it off, clean up, and put tools back.
- Items left outside storage areas, or on project tables without a reservation, may be thrown away.
- No running or horseplay, and never prop doors open or let anyone in.

## How to get access, step by step

- Access is managed through an online system called FOM (Facility Online Manager), at fom.engineering.txstate.edu. FOM is used to sign up, take quizzes, track trainings, reserve machines and turn them on.
- Ingram School of Engineering program directors and staff get badge access directly, with no request needed.
- Step 1: read the Makerspace Policies and Procedures on the Makerspace website.
- Step 2: sign the Ingram Hall Makerspace Participation Agreement on the Makerspace forms page. It is renewed every academic year (September 1 to August 31).
- Step 3: for walk-in use, student organizations or personal projects, also sign the Release of Liability (renewed every year, with a separate version for people under 18) and the Photograph Release (one time only).
- Step 4: log in to FOM with your TXST NetID and Duo. Pick any discipline. Pick your instructor or research advisor as your supervisor. If they aren't listed, you can pick "Bobcat, Boko", but that account can't use equipment until someone adds you.
- Step 5: in FOM, click "Request Access to New Resource" and take the Makerspace Policy Quiz. You need 100 percent, but there's no time limit and you can retry as many times as you like.
- Step 6: register your TXST ID card at the self-service kiosk at the Makerspace entrance: log in to FOM there, open My Profile, click the User ID Card field, and tap your card on the scanner.
- Step 7: request access to the PawPrint Studio room in FOM. Staff take about two business days to process your forms.
- To use machines, you also need a financial account in FOM, which depends on why you're there.
- For a class or senior design team: the instructor requests a course account with the Course Usage Request or Senior Capstone Request form, then adds students. Students just log in to FOM once and ask their instructor.
- For research: the faculty advisor (the PI) submits a Research Usage Request form, and then adds students and researchers in FOM.
- For a student organization: an officer or faculty advisor submits a Student Organization Usage Request form. Then the president adds members in FOM.
- For a personal project: you submit the Personal Project Usage Request form yourself, with a faculty or staff mentor, and pay for machine time and materials.
- New accounts usually take about one business day to set up after everyone signs.
- You must log in to FOM at least once before anyone can add you to a course, project or organization.

## Training for each machine

- In FOM, each machine shows the trainings it needs. If something is missing, FOM tells you which quiz or certificate to complete first.
- All FOM quizzes need a perfect score, with unlimited attempts. The study material is in the Documents tab in FOM.
- FOM policy quizzes must be renewed every 150 days.
- In-person machine training expires if you don't use that machine for 180 days. Every use resets the clock.
- Online certificates, like LinkedIn Learning, never expire for training purposes. LinkedIn Learning is free for TXST students, faculty and staff. Upload certificates with the online certificate upload form on the Makerspace forms page.
- Prusa Core One and Prusa MINI printers: the Fused Filament Fabrication quiz in FOM, plus the LinkedIn Learning course "Additive Manufacturing: Optimizing 3D Prints".
- Prusa XL and the multi-material Core One: those two, plus the Multi-Material FFF quiz.
- xTool P2S laser cutters: the Makerspace Policy Quiz, PawPrint Studio access, and the xTool quiz.
- Industrial Area: you first need PawPrint Studio access and the Industrial Area quiz.
- Industrial machines, like the lathes, need in-person training with staff. Request the machine in FOM and send a message with your class or project and your available times to schedule a session.
- Other recommended courses: Understanding Personal Protective Equipment, Learning Mastercam, and Introduction to Mill and Lathe Operation on LinkedIn Learning. For the Haas CNC machines, there's the free Haas Certification Program at learn.haascnc.com.
- The Makerspace website has an Equipment Training Guide with flowcharts and an interactive dashboard, and instructional videos on FOM onboarding and 3D printing.

## 3D printing in the PawPrint Studio

- The PawPrint Studio has 19 Prusa 3D printers: 12 Prusa Core One printers, one more Core One for bring-your-own-filament (BYOF), 2 Prusa MINI printers, and 4 Prusa XL printers. There is also a multi-material Core One.
- Prusa Core One: an enclosed printer with a build area of about 25 by 22 by 27 centimeters. It is the main workhorse printer.
- Prusa MINI: a small printer, about 18 by 18 by 18 centimeters, good for small parts.
- Prusa XL: a large printer, about 36 by 36 by 36 centimeters, with 5 print heads, so one print can use up to five colors or materials.
- Multi-material Core One: a Core One with a multi-material unit (MMU) for multi-color prints. Only staff may load its filament.
- Filament: the regular printers only use PLA supplied by the Makerspace, at 2 cents per gram. The BYOF printer uses only your own filament, of any type the printer can handle. Ask an MST about material compatibility.
- Step 1, slice: open Orca Slicer on a Makerspace computer, start a new project and add your STL or 3MF file. Pick the right printer and the "PawPrint Studio Default" settings, set the material to PLA, and use auto orient or lay on face so the part sits flat. Click Slice Plate, note the print time and filament grams, and export the G-code file.
- Step 2, reserve: in FOM, request access to a printer, open its calendar and click a start time. Choose your financial account, and set the end time to the slicer's print time plus 45 minutes for warm-up and cleanup. Enter the grams of filament.
- Step 3, log on: click your reservation in FOM and press Logon. This turns the printer on. If you don't log on within 30 minutes of your start time, the reservation is cancelled.
- Step 4, print: on the TXST network, go to 3dprint.engineering.txstate.edu and log in with your NetID. Click your printer, check the bed is clear and there's enough filament, upload your G-code, load it, and press Print.
- Step 5, watch: most failures happen in the first 30 minutes, so stay and watch the start. After that, you can leave and watch on the live camera feed.
- Step 6, finish: take your part off by gently flexing the build plate. Never use tools on the print bed. Clean the plate, put it back, then press Logoff in FOM, which turns the printer off.
- Printers turn off automatically 4 hours after your reserved end time, and the next person with a reservation can log you off, so set your time correctly. You can extend if no one is booked after you.
- You may reserve several printers at once. Files on the printers are deleted weekly, so keep your own copies.
- There is a 30-minute minimum charge for every print.

## Laser cutting with the xTool P2S

- The PawPrint Studio has two xTool P2S lasers. Each is a 55 watt desktop CO2 laser cutter and engraver.
- They cut, score and engrave wood, acrylic, cardboard, leather and similar materials.
- How it works: draw a sketch in a CAD program like SolidWorks and save it as an SVG or DXF file. Open xTool Studio, import the file, choose the bed type (usually the honeycomb panel) and your material, and mark each line as cut, score or engrave.
- Log on to the laser in FOM, which turns it on and calibrates it. Load your material, hold it down with the magnetic clips, click Start, and press the button on the laser.
- Keep the lid closed the whole time and stay with the machine. Some smoke is normal, but a flame is not.
- If a fire starts: stop the job, keep the lid closed, and tell staff. The emergency stop button is on the right side of the machine.
- Never cut PVC, vinyl or other chlorine plastics, because they release toxic chlorine gas. Never put mirrors or polished metal inside, and never cut a material you can't identify.
- When done, wait a couple of minutes with the lid closed for the fumes to clear, then log off in FOM and clean up.

## The other machines

These descriptions combine the Makerspace's machine list with the manufacturers'
general specifications. The exact setup of each machine here may differ.

- Haas VF-2: a 3-axis vertical CNC mill, an industry-standard machine that cuts metal or plastic parts by moving a spinning cutter under computer control. Its travel is about 30 by 16 by 20 inches.
- Haas VF-3, set up for 5-axis machining: a larger Haas mill where the part can also tilt and rotate, so complex shapes can be cut from many sides in one setup.
- Haas ST-20Y: a CNC lathe that spins the material to cut round parts like shafts. Its Y-axis and live tooling can also drill and mill off-center features.
- Tormach PCNC 440: a compact CNC mill, smaller and easier to learn on than the Haas machines.
- Manual mills and Kingston manual lathes: traditional machines controlled by hand wheels. They teach the basics of machining.
- Shark CNC router: cuts and carves wood, plastic and foam sheets.
- WardJet waterjet: an industrial waterjet that cuts metal, stone, glass and plastic with ultra-high-pressure water mixed with garnet abrasive. It cuts without heat, so the material doesn't warp.
- Wazer waterjet: a compact desktop waterjet for smaller sheets of metal, glass, tile and plastic.
- Torchmate CNC plasma table: cuts steel sheet with a computer-guided plasma torch, fast for brackets and plates.
- Fiber laser: a laser built for marking and engraving metal, like serial numbers and logos.
- Markforged Mark Two: an industrial composite 3D printer. It prints a tough nylon-carbon material called Onyx, and can lay continuous carbon fiber, Kevlar or fiberglass inside parts, making them strong enough to replace some aluminum parts.
- Welding bay: welding stations for metal frames, chassis and structures.
- Woodshop: tools for traditional woodworking.
- Electronics workbenches and a PCB maker for building circuits and circuit boards.

## How much it costs

From the Spring 2026 rates page. Prices can change, so check the rates page. Internal
rates are for class, research, senior design and student organization work billed to
a TXST account. External rates are for everyone else. Rates are per hour, with a
30-minute minimum.

- 3D printers, per hour internal: Prusa Core One 1 dollar, Core One BYOF 2 dollars, Prusa MINI 1 dollar, Prusa XL 2 dollars, Markforged Mark Two 4 dollars. External is 1.5 times that.
- Lasers, per hour internal: xTool 6 dollars, fiber laser 24 dollars. External: 9 and 36 dollars.
- CNC and cutting, per hour internal: Shark router 15, Wazer 15, Tormach 19, Torchmate 21, Haas VF-2 30, Haas VF-3 31, Haas ST-20Y 32, WardJet 43 dollars. External is about 1.5 times that.
- Manual machines and welding, per hour internal: manual mill 17, manual lathe 19, welding bay 20 dollars. External: 26, 29 and 30 dollars.
- Materials: PLA 2 cents per gram. Markforged: Onyx 25 cents, fiberglass 1 dollar 60, Kevlar 2 dollars, high-temperature fiberglass 2 dollars, and carbon fiber 4 dollars per cubic centimeter.
- Internal on-site use is capped at 450 dollars a month per project, class section, senior design group or research award, not counting materials. Student organizations get one cap per 15 members.
- Students on personal projects pay external rates, unless a faculty mentor sponsors the project, which can qualify them for internal rates.
- Paying invoices by credit card adds a 3 percent fee. Unpaid balances can lead to an academic hold.
- Please acknowledge the Ingram Hall Makerspace in papers and grant applications that used its equipment or staff.

## Student organizations

- The Makerspace is the main fabrication hub for Bobcat Racing, Bobcat Aerospace, and the IEEE Robotics and Automation Society.
- Bobcat Racing is Texas State's Formula SAE team. Students design, build and race a small formula-style race car against university teams from around the world. It runs like a small car company, so students of any major can help. Contact: bobcatracing@txstate.edu.
- Bobcat Racing was revived in 2021 after COVID and builds its car in the Makerspace. Its 2026 car uses a Yamaha FZ6 motorcycle engine.
- Bobcat Aerospace is Texas State's first and largest high-power rocketry club, founded in fall 2021. It builds rockets for competitions like the Spaceport America Cup in New Mexico, aiming for about 10,000 feet. Any major can join.
- The IEEE Robotics and Automation Society student chapter builds robotics projects in the Makerspace.

## Projects happening now (fall 2026 senior design)

- Nearly all senior design projects are built and stored in the Makerspace. Teams show their work at Senior Design Day at the end of every fall and spring semester, and great projects are displayed near the Makerspace entrance.
- The Makerspace itself sponsors a project: a vibration and sound sensing system for the Makerspace's manual milling machines, to predict surface finish and tool wear.
- A chip handling system for the Haas VF-2 mill, to remove and sort metal chips when switching materials.
- A smart sediment trap that cleans garnet and dirt out of waterjet wastewater.
- Two soft robotic grippers that pick up peaches without bruising them, for a Universal Robots UR7e collaborative robot arm. One uses inflatable silicone fingers and a camera, the other uses suction.
- For Bobcat Racing: a new braking system with a test rig, and a final drive system for the 2026 car.
- The C.A.T. Crawler, a rover drive system for NASA's Psyche asteroid mission.
- A precision pesticide sprayer for an automated FarmBot vertical farm.
- Several teams are designing new TXST T-shirt launchers for game days.
- Others include a sit-to-stand trainer for physical therapy patients, and a training model of a stomach for doctors, sponsored by Boston Scientific.

## Past projects (spring 2025 senior design)

- A lunar concrete mixer that makes "moon bricks" from fake moon soil, sponsored by NASA MINDS and the Ingram Hall Makerspace.
- The Artistic Automaton: a robot arm that draws with a pen, from a photo or from a phone app.
- Other robots: an Artist Robot, a Push-Pull Bot, a Line Following Bot and the Speedy Liner.
- Pleiades Electra, an antenna array that lets Texas State talk to satellites in low Earth orbit.
- A radiation-tolerant laptop for space crews, and the Ouroboros guitar looper pedal.
- A manufacturing team built critical parts for Bobcat Racing's 2025 race car.
- Earlier, in a CAD/CAM class, students learned to program CNC mills and then ran their own programs on the machines.
- The Makerspace has hosted workshops for new students, where groups made a small custom project with a laser cutter, laser engraver or 3D printer.

## People

- The Makerspace has a team of about a dozen staff and student workers, listed on the "Our Team" page of its website.
- Abhimanyu Sharotry, a research scientist at the Ingram School of Engineering, is on the Makerspace team. He studies digital twins and the simulation of manufacturing systems, advises the soft robotic gripper teams, and has been Bobcat Racing's faculty advisor.
- Brian Earle on the Makerspace team is known as "the Haas guy", the go-to person for the Haas CNC machines.

## Tips for visitors

- A great first project is a 3D print or a laser-cut design in the PawPrint Studio.
- Start by reading the policies, signing the participation agreement and taking the Makerspace Policy Quiz in FOM.
- The Makerspace accepts donations through the Texas State giving site, to help buy equipment for future engineers.
