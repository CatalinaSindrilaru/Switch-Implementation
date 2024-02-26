#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

port_states = {} # key = interface, value = port state
own_bridge_id = 0
root_bridge_id = 0
root_path_cost = 0
root_port = 0
type_interfaces = {} # key = interface name, value = T or value

BPDU_MULTICAST_MAC = b'\x01\x80\xc2\x00\x00\x00'
LLC_LENGTH = struct.pack('!H', 52) # H means packed as unsigned short (2 bytes)
LLC_HEADER = b'\x42\x42\x03' # DSAP | SSAP | Control
BPDU_HEADER = b'\x00\x00\x00\x00' # Protocol Identifier | Protocol Version Identifier | BPDU Type 


def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def send_bdpu_every_sec():

    while True:

        global port_states
        global own_bridge_id
        global root_bridge_id
        global type_interfaces

        if root_bridge_id == own_bridge_id:
            for trunk_port in port_states:
                if len(type_interfaces) == 0 or type_interfaces[get_interface_name(trunk_port)] != 'T':
                    continue
                root_bridge_id = own_bridge_id
                sender_bridge_id = own_bridge_id
                sender_path_cost = 0

                dest_mac = BPDU_MULTICAST_MAC
                src_mac = get_switch_mac()

                bpdu_config = {
                    'flags': b'\x00',
                    # Q means 8 bytes, L means 4 bytes, H means 2 bytes
                    'root_bridge_id': struct.pack('!Q', root_bridge_id),
                    'root_path_cost': struct.pack('!L', sender_path_cost),
                    'bridge_id': struct.pack('!Q', sender_bridge_id),
                    'port_id': struct.pack('!H', trunk_port),
                    'message_age': struct.pack('!H', 0),
                    'max_age': struct.pack('!H', 20),
                    'hello_time': struct.pack('!H', 2),
                    'forward_delay': struct.pack('!H', 15),
                }

                bpdu = dest_mac + src_mac + LLC_LENGTH + LLC_HEADER + BPDU_HEADER + b''.join(bpdu_config.values())
                send_to_link(trunk_port, bpdu, len(bpdu))

        time.sleep(1)


def send_frame_from_access(source_interface, dest_interface, data, length):
    # verify if the dest interface is trunk or access
    if type_interfaces[get_interface_name(dest_interface)] == 'T':
        # create new frame with vlan tag
        vlan = int(type_interfaces[get_interface_name(source_interface)]) 
        tagged_frame = data[0:12] + create_vlan_tag(vlan) + data[12:]
        send_to_link(dest_interface, tagged_frame, length + 4)
    else:
        vlan_interface_to_send = int(type_interfaces[get_interface_name(dest_interface)])
        vlan_source = int(type_interfaces[get_interface_name(source_interface)])
        # verify if the vlan is the same
        if vlan_interface_to_send == vlan_source:
            send_to_link(dest_interface, data, length)


def send_frame_from_trunk(source_vlan, dest_interface, data, length):
    # verify if the dest interface is trunk or access
    if type_interfaces[get_interface_name(dest_interface)] == 'T':
        send_to_link(dest_interface, data, length)
    else:
        vlan_interface_to_send = int(type_interfaces[get_interface_name(dest_interface)])
        if vlan_interface_to_send == source_vlan:
            untagged_frame = data[0:12] + data[16:]
            new_length = length - 4
            send_to_link(dest_interface, untagged_frame, new_length)


def main():

    global port_states
    global own_bridge_id 
    global root_bridge_id
    global root_path_cost 
    global root_port 
    global type_interfaces
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1
    switch_id = sys.argv[1]

    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)

    print("# Starting switch with id {}".format(switch_id), flush=True)
    print("[INFO] Switch MAC", ':'.join(f'{b:02x}' for b in get_switch_mac()))

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target=send_bdpu_every_sec)
    t.start()

    # Printing interface names
    for i in interfaces:
        print(get_interface_name(i))

    # create mac address table with dictionary
    mac_table = {} # key = mac address, value = interface

    # read info for the switch from the ./config/switches.cfg file
    filepath = './configs/switch' + switch_id + '.cfg'
    priority = None

    with open(filepath) as fp:
        priority = int(fp.readline().strip())
        for line in fp:
            interface_name, vlan_or_trunk = line.strip().split(' ')
            type_interfaces[interface_name] = vlan_or_trunk

    # initialize port states for STP
    for i in interfaces:
        if type_interfaces[get_interface_name(i)] == 'T':
            port_states[i] = 'BLOCKING'
        else:
            port_states[i] = 'DESIGNATED_PORT'

    own_bridge_id = priority
    root_bridge_id = own_bridge_id
    root_path_cost = 0

    if own_bridge_id == root_bridge_id:
        for port in port_states:
            port_states[port] = 'DESIGNATED_PORT'

    while True:

        interface, data, length = recv_from_any_link()
        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac = ':'.join(f'{b:02x}' for b in src_mac)

        if dest_mac == ':'.join(f'{b:02x}' for b in BPDU_MULTICAST_MAC):
            # parse BPDU
            bpdu = data[21:]
            bpdu_config = {
                'flags': bpdu[0:1],
                'root_bridge_id': bpdu[1:9],
                'root_path_cost': bpdu[9:13],
                'bridge_id': bpdu[13:21],
                'port_id': bpdu[21:23],
                'message_age': bpdu[23:25],
                'max_age': bpdu[25:27],
                'hello_time': bpdu[27:29],
                'forward_delay': bpdu[29:31],
            }

            if int.from_bytes(bpdu_config['root_bridge_id'], 'big') < root_bridge_id:

                prev_root_bridge_id = root_bridge_id  # save the previous root bridge id
                root_bridge_id = int.from_bytes(bpdu_config['root_bridge_id'], 'big')
                root_path_cost = int.from_bytes(bpdu_config['root_path_cost'], 'big') + 10
                root_port = int.from_bytes(bpdu_config['port_id'], 'big')

                if own_bridge_id == prev_root_bridge_id:
                    for i in interfaces:
                        if type_interfaces[get_interface_name(i)] == 'T' and i != root_port:
                            port_states[i] = 'BLOCKING'

                if port_states[root_port] == 'BLOCKING':
                    port_states[root_port] = 'LISTENING'
                        
                bpdu_config['bridge_id'] = struct.pack('!Q', own_bridge_id) # sender bridge id changed
                bpdu_config['root_path_cost'] = struct.pack('!L', root_path_cost) # sender path cost changed

                for i in interfaces:
                    if i != interface:
                        if type_interfaces[get_interface_name(i)] == 'T':
                            dest_mac = BPDU_MULTICAST_MAC
                            src_mac = get_switch_mac()
                            bpdu_config['port_id'] = struct.pack('!H', i) # H means 2 bytes

                            bpdu = dest_mac + src_mac + LLC_LENGTH + LLC_HEADER + BPDU_HEADER + b''.join(bpdu_config.values())
                            send_to_link(i, bpdu, len(bpdu))

            elif bpdu_config['root_bridge_id'] == root_bridge_id:

                if interface == root_port and int.from_bytes(bpdu_config['root_path_cost'], 'big') + 10 < root_path_cost:
                    root_path_cost = int.from_bytes(bpdu_config['root_path_cost'], 'big') + 10

                elif interface != root_port:
                    if int.from_bytes(bpdu_config['root_path_cost'], 'big') > root_path_cost:
                        if port_states[interface] == "BLOCKING":
                            port_states[interface] = "LISTENING"

            elif int.from_bytes(bpdu_config['bridge_id'], 'big') == own_bridge_id:  # if the sender is me, means that is a loop
                port_states[interface] = "BLOCKING"  
            else:
                pass # discard the BPDU

            if own_bridge_id == root_bridge_id: # if i am the root bridge
                for i in interfaces:
                    if type_interfaces[get_interface_name(i)] == 'T':
                        port_states[i] = 'DESIGNATED_PORT'

        else:
            mac_table[src_mac] = interface # add src mac to mac table

            if dest_mac in mac_table and port_states[mac_table[dest_mac]] != 'BLOCKING':
                # verify if the frame came from access or trunk
                if vlan_id == -1: # came from access
                    send_frame_from_access(interface, mac_table[dest_mac], data, length)
                else: # came from trunk
                    send_frame_from_trunk(vlan_id, mac_table[dest_mac], data, length)
            else:
                # broadcast to all interfaces expect the one it came from
                for i in interfaces:
                    if i != interface and port_states[i] != 'BLOCKING':
                        # verify if the frame came from access or trunk
                        if vlan_id == -1: # came from acess
                            send_frame_from_access(interface, i, data, length)
                        else: # came from trunk
                            send_frame_from_trunk(vlan_id, i, data, length)

if __name__ == "__main__":
    main()


# TASK 1
# # TODO: Implement forwarding with learning
# mac_table[src_mac] = interface
#
# if dest_mac in mac_table:
#     # send to interface
#     send_to_link(mac_table[dest_mac], data, length)
# else:
#     # broadcast to all interfaces expect the one it came from
#     for i in interfaces:
#         if i != interface:
#             send_to_link(i, data, length)

# TASK 2
# TODO: Implement VLAN support
#
# mac_table[src_mac] = interface
#
# if dest_mac in mac_table:
#     if vlan_id == -1: # a venit de pe acess
#         if type_interfaces[get_interface_name(mac_table[dest_mac])] == 'T':
#             vlan = int(type_interfaces[get_interface_name(interface)]) 
#             tagged_frame = data[0:12] + create_vlan_tag(vlan) + data[12:]
#             send_to_link(mac_table[dest_mac], tagged_frame, length + 4)
#         else:
#             vlan_interface_to_send = int(type_interfaces[get_interface_name(mac_table[dest_mac])])
#             vlan_source = int(type_interfaces[get_interface_name(interface)])
#             if vlan_interface_to_send == vlan_source:
#                 send_to_link(mac_table[dest_mac], data, length)

#     else: 
#         if type_interfaces[get_interface_name(mac_table[dest_mac])] == 'T':
#             send_to_link(mac_table[dest_mac], data, length)
#         else:
#             vlan_interface_to_send = int(type_interfaces[get_interface_name(mac_table[dest_mac])])
#             if vlan_interface_to_send == vlan_id:
#                 untagged_frame = data[0:12] + data[16:]
#                 new_length = length - 4
#                 send_to_link(mac_table[dest_mac], untagged_frame, new_length)
# else:
#     for i in interfaces:
#         if i != interface:
#             if vlan_id == -1:
#                 if type_interfaces[get_interface_name(i)] == 'T':
#                     vlan = int(type_interfaces[get_interface_name(interface)]) # gasesc vlan ul de pe interfata sursa
#                     tagged_frame = data[0:12] + create_vlan_tag(vlan) + data[12:]
#                     send_to_link(i, tagged_frame, length + 4)
#                 else:
#                     vlan_interface_to_send = int(type_interfaces[get_interface_name(i)])
#                     vlan_source = int(type_interfaces[get_interface_name(interface)])
#                     if vlan_interface_to_send == vlan_source:
#                         send_to_link(i, data, length)
#             else: 
#                 if type_interfaces[get_interface_name(i)] == 'T':
#                     send_to_link(i, data, length)
#                 else:
#                     vlan_interface_to_send = int(type_interfaces[get_interface_name(i)])
#                     if vlan_interface_to_send == vlan_id:
#                         untagged_frame = data[0:12] + data[16:]
#                         new_length = length - 4
#                         send_to_link(i, untagged_frame, new_length)