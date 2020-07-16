#!/usr/bin/env python3

"""
Written by robertoszek
Github: https://github.com/robertoszek
Email: robertoszek@robertoszek.xyz

vSphere Python SDK program to calculate free space in a Datastore cluster (StoragePod) taking into account space
reserved during the period of time (in hours) specified and keeping track of them using a helper JSON file
"""

import argparse
import json
import os.path
import datetime
import time
import ssl
import atexit

from pyVmomi import vim
from pyVmomi import vmodl
from pyVim import connect


def get_args():
    """
    Supports the command-line arguments listed below.
    """
    parser = argparse.ArgumentParser(
        description='Process args for retrieving all the Virtual Machines')

    parser.add_argument('-s', '--host',
                        required=True, action='store',
                        help='Remote host to connect to')

    parser.add_argument('-o', '--port',
                        type=int, default=443,
                        action='store', help='Port to connect on')

    parser.add_argument('-u', '--user', default="myUser",
                        action='store',
                        help='User name to use when connecting to host')

    parser.add_argument('-p', '--password',
                        default="myPassword", action='store',
                        help='Password to use when connecting to host')

    parser.add_argument('-d', '--dscluster', required=True, action='store',
                        help='Name of vSphere Datastore Cluster')

    parser.add_argument('-r', '--requiredspace', required=True, action='store',
                        help='Space required for the deployment of the virtual machine')

    parser.add_argument('-t', '--time', default=8, action='store',
                        help='How many hours to take into account when looking at previous reservations')

    args = parser.parse_args()
    return args


def sizeof_fmt(num):
    """
    Returns the human readable version of a file size
    :param num:
    :return:
    """
    for item in ['bytes', 'KB', 'MB', 'GB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, item)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')


def print_fs(host_fs, dsc_reserved_space, dsc_free_after, dsc_freespace_percent_after):
    """
    Prints the host file system volume info
    :param host_fs:
    :param dsc_reserved_space:
    :param dsc_free_after:
    :param dsc_freespace_percent_after:
    :return:
    """
    print("{}\t{}\t".format("Datastore: ", host_fs.name))
    print("{}\t{}\t".format("Capacity:  ", sizeof_fmt(host_fs.summary.capacity)))
    print("{}\t{}\t".format("FreeSpace: ", sizeof_fmt(host_fs.summary.freeSpace)))
    print("{}\t{}\t".format("FreeSpace percent: ",
                            ("{:.2f}".format((host_fs.summary.freeSpace / host_fs.summary.capacity) * 100))))
    print("{}\t{}\t".format("ReservedSpace (GB): ", dsc_reserved_space))
    print("{}\t{}\t".format("Free Space After (GB): ", ("{:.2f}".format(dsc_free_after / 1073741824))))
    print("{}\t{}\t".format("Free Percent Space After:  ", dsc_freespace_percent_after))


def get_objs(content, vimtype, name=None):
    """
    Returns all the objects for a specified vimType
    :param content:
    :param vimtype:
    :param name:
    :return:
    """
    cv = content.viewManager.CreateContainerView(
        content.rootFolder, [vimtype], recursive=True)
    try:
        return [item for item in cv.view]  # or just return cv.view
    finally:
        cv.Destroy()


def get_object_match(content, vimtype, name):
    """
    Returns the object that matches the name provided
    :param content:
    :param vimtype:
    :param name:
    :return:
    """
    obj = {}
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    try:
        for managed_object_ref in container.view:
            if managed_object_ref.name == name:
                return managed_object_ref
    finally:
        container.Destroy()


def get_default_json(host, dscluster, requiredspace, vm_name=None):
    """
    Creates a dict object with default values and returns it
    """
    print('No json file found, inserting default values...')
    defaults = {host: []}
    defaults[host].append({
        dscluster: []
    })
    defaults[host][0][dscluster].append({
        'reservation': []
    })
    defaults[host][0][dscluster][0]['reservation'].append({
        'timestamp': datetime.datetime.fromtimestamp(datetime.datetime.now().timestamp()).isoformat(),
        'requiredSpaceGB': requiredspace,
        'vmName': vm_name
    })
    return defaults


def main():
    args = get_args()
    reservation_file = 'DSCFreeSpacePercentReservation.json'
    lock_file = 'DSCFreeSpacePercentReservation.lck'
    end_time = datetime.datetime.now() + datetime.timedelta(minutes=2)
    # Wait for the lock file to disappear for 2 minutes and then forcefully remove after if it didn't
    while True:
        if datetime.datetime.now() >= end_time:
            print("Giving up waiting, removing the lock and hoping for the best...")
            if os.path.isfile(lock_file):
                os.remove(lock_file)
            break
        if os.path.isfile(lock_file):
            print("Lock file found, waiting for a previous run to finish...")
            time.sleep(5)
            continue
        else:
            break
    # Create lock file
    f = open(lock_file, "w")
    f.close()
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ssl_context.verify_mode = ssl.CERT_NONE
    try:
        service_instance = connect.SmartConnect(host=args.host,
                                                user=args.user,
                                                pwd=args.password,
                                                port=int(args.port),
                                                sslContext=ssl_context)
        if not service_instance:
            print("Could not connect to the specified host using specified "
                  "username and password")
            exit(1)
        # Disconnect
        atexit.register(connect.Disconnect, service_instance)

        content = service_instance.RetrieveContent()
        # Datastore clusters are called StoragePods
        cluster = get_object_match(content, [vim.StoragePod], args.dscluster)
        dsc_capacity = cluster.summary.capacity
        dsc_freespace = cluster.summary.freeSpace

        # Check if file exists
        if os.path.isfile(reservation_file):
            with open(reservation_file) as json_file:
                data = json.load(json_file)
        else:
            data = get_default_json(args.host, args.dscluster, args.requiredspace)

        # Insert new reservation
        if args.host not in data:
            data[args.host] = []
            data[args.host].append({
                args.dscluster: []
            })
        if args.dscluster not in data[args.host][0]:
            data[args.host][0].update({
                args.dscluster: []
            })
        if not data[args.host][0][args.dscluster]:
            data[args.host][0][args.dscluster].append({
                'reservation': []
            })

        data[args.host][0][args.dscluster][0]['reservation'].append({
            'timestamp': datetime.datetime.fromtimestamp(datetime.datetime.now().timestamp()).isoformat(),
            'requiredSpaceGB': args.requiredspace,
            'vmName': ''
        })

        # Calculate space after the reservations
        dsc_reserved_space = 0
        # Iterate from a copy ([:]) so we can remove items from the original list
        for item in data[args.host][0][args.dscluster][0]['reservation'][:]:
            date_old = datetime.datetime.fromisoformat(item['timestamp'])
            date_now = datetime.datetime.now()
            difference = date_now - date_old
            hours = divmod(difference.total_seconds(), 3600)[0]
            if hours < args.time:
                dsc_reserved_space += float(item['requiredSpaceGB'])
            else:
                data[args.host][0][args.dscluster][0]['reservation'].remove(item)

        dsc_free_after = dsc_freespace - (dsc_reserved_space * 1073741824)  # convert into same order
        dsc_freespace_percent_after = ("{:.2f}".format((dsc_free_after / dsc_capacity) * 100))

        print_fs(cluster, dsc_reserved_space, dsc_free_after, dsc_freespace_percent_after)

        if float(dsc_freespace_percent_after) > 10:
            print("OK, free percent after provisioning: ", dsc_freespace_percent_after)
            # Output json data to file
            with open(reservation_file, 'w') as outfile:
                json.dump(data, outfile, indent=4)
            # Clean up lock
            if os.path.isfile(lock_file):
                os.remove(lock_file)
        else:
            print("ERROR: Cluster datastore free space percent not enough for provisioning. We can't continue with "
                  "the process.")
            # Clean up lock
            if os.path.isfile(lock_file):
                os.remove(lock_file)
            exit(1)
    except vmodl.MethodFault as error:
        print("Caught vmodl fault : " + error.msg)
        # Clean up lock
        if os.path.isfile(lock_file):
            os.remove(lock_file)
        exit(1)
    finally:
        # Clean up lock
        if os.path.isfile(lock_file):
            os.remove(lock_file)


if __name__ == '__main__':
    main()
