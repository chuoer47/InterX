# Cisco Meraki MV Camera Installation Guide

## Camera Overview

This is a networked camera that is exceptionally simple to deploy and configure due to its integration into the dashboard and the use of cloud augmented edge storage. The MV family eliminates the complex and costly servers and video recorders required by traditional solutions which removes the limitations typically placed on video surveillance deployments.

## Package Contents

In addition to the MV camera, the following are provided:

![Illustration](插图/Security_Camera_01.jpg)

> Package hardware: wall screws, wall anchors, Torx tools, and other mounting hardware.

![Illustration](插图/Security_Camera_02.jpg)

> Package hardware: drop-ceiling T-rail mount clips and related screws/spacers.

## Pre-Install Preparation

You should complete the following steps before going on-site to perform an installation.

## Configure Your Network in Dashboard

The following is a brief overview only of the steps required to add a camera to your network. For detailed instructions about creating, configuring, and managing camera networks, refer to the online documentation.

1. Log in to the website. If this is your first time, create a new account.

2. Find the network to which you plan to add your cameras or create a new network.

3. Add your cameras to your network. You will need your order number (found on your invoice) or the serial number of each camera, which looks like Qxxx-xxxx-xxxx, and is found on the bottom of the unit.

4. Verify that the camera is now listed under Cameras > Monitor > Cameras.

## Check and Configure Firewall Settings

If a firewall is in place, it must allow outgoing connections on particular ports to particular IP addresses. The most current list of outbound ports and IP addresses for your particular organization can be found here

## DNS Configuration

Each camera will generate a unique domain name to allow for secured direct streaming functionality. These domain names resolve an A record for the private IP address of the camera. Any public recursive DNS server will resolve this domain. If utilizing an on-site DNS server, please whitelist \*.devices.direct or configure a conditional forwarder so that local domains are not appended to \*.devices.meraki.direct and that these domain requests are forwarded.

## Assigning IP Addresses

At this time, the camera does not support static IP assignment. Camera units must be added to a subnet that uses DHCP and has available DHCP addresses to operate correctly.

## Installation Instructions

**NOTE:** Each camera comes with an instruction pamphlet within the box. This pamphlet contains detailed step-by-step guides and images to assist in the physical install of the camera. A PDF of the pamphlet can be found here.

**Note:** During first time setup, the camera will automatically update to the latest stable firmware. Some features may be unavailable until this automatic update is completed. This process may take up to 20 minutes due to enabling of whole disk encryption.

## Wall Mounting Instructions

For most mounting scenarios, the wall mount provides a quick, simple, and flexible means of mounting your device. The installation should be done in a few simple steps:

1. Leave protective plastic sticker on camera bubble

![Illustration](插图/Manual33_0.jpg)

2. Use the template to determine mounting hole locations before screwing in the mount plate. Peel backing from mount template to stick on wall.

![Illustration](插图/Manual33_1.jpg)

3. Screw the mounting plate onto the wall in pre-determined locations. Use template holes marked with the letter "A" for standard wall mounting.

![Illustration](插图/Manual33_2.jpg)

4. Connect PoE cable to camera. For cords that will exit the top of the camera, loop the cable inside the camera as shown.

![Illustration](插图/Manual33_3.jpg)

5. Slide camera over top of mount plate and slide down into mount plate hooks. Secure with safety screw.

![Illustration](插图/Manual33_4.jpg)

6. Turn bubble counterclockwise to unlock. Hinge bubble off of body to remove.

![Illustration](插图/Manual33_5.jpg)

7. Pinch near thumb screws and pull straight away from the camera to remove lens guard.

![Illustration](插图/Manual33_6.jpg)

8. Aim the lens. Look through the camera on the Dashboard to fine tune the picture. The camera sensor and lens unit can be physically tilted through a range of 65 degrees, rotated through a range of 350 degrees, and panned through a range of 350 degrees. The image can only be rotated by 180 degrees in software and no other adjustments can be made. Zoom and focus can be adjusted remotely and cannot be adjusted physically on the camera.

![Illustration](插图/Manual33_7.jpg)

9. Replace lens guard and bubble. Turn bubble clockwise to lock.

![Illustration](插图/Manual33_8.jpg)

10. Remove protective plastic sticker. Check LED function. Use the Dashboard to adjust camera focus and configure other settings.

![Illustration](插图/Manual33_9.jpg)

## T-rail Mounting Instructions

To mount your camera on a drop ceiling T-rail, use the included hardware. The hardware can be used to mount to most 9/16", 15/16", or 1 1/2" T-rails.

1. Using the dashed lines on the mount plate template as a guide, set the proper spacing of the clips.

![Illustration](插图/Manual33_10.jpg)

2. Tighten the set screws on the T-rail clips and secure them using a 5/64" (2 mm) hex key.

![Illustration](插图/Manual33_11.jpg)

3. Attach the mount plate to the T-rail clips using the mount plate holes marked with `G`.

![Illustration](插图/Manual33_12.jpg)

4. Attach the T-rail clips to the T-rail by rotating them and snapping them into place as shown. The black foam pads should be compressed slightly after installation.

![Illustration](插图/Manual33_13.jpg)

Standard 6-32 x 4 mm T-rail screws.

![Illustration](插图/Manual33_14.jpg)

Modifications for recessed T-rail.

## Powering the Camera

Remove the cable guard and route the Ethernet cable from an active port on an 802.3af PoE switch or PoE injector.

**NOTE:** Power over Ethernet supports a maximum cable length of 300 ft (100 m).

## LED Indicator

Your camera is equipped with an LED light on the front of the unit to convey information about system functionality and performance:

- Flashing green (2 second interval): MV is upgrading or initializing for the first time.
- Solid green: MV is operating nominally.
