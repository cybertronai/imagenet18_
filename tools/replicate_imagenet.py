#!/usr/bin/env python

# Downloads imagenet and replicates it across multiple disks
#
# Script to initialize a set of high-performance volumes with ImageNet data
# 
# replicate_imagenet.py --replicas 8
# replicate_imagenet.py --replicas 8 --volume-offset=8
#
# or
#
# replicate_imagenet.py --replicas 16 --zone=us-east-1b
# Creates volumes: imagenet_00, imagenet_01, imagenet_02, ..., imagenet_15
#
# ImageNet data should follow structure as in
# https://github.com/diux-dev/cluster/tree/master/pytorch#data-preparation
# (paths replace ~/data with /)
#
# steps to create snapshot:
# create blank volume (ec2.create_volume())
# attach it to an existing instance with ImageNet under data, then
# sudo mkfs -t ext4 /dev/xvdf
# mkdir data
# sudo mount /dev/xvdf data
# sudo chown data `whoami`
# cp -R data0 data
# snapshot = ec2.create_snapshot(Description=f'{u.get_name(vol)} snapshot',
# VolumeId=vol.id,)

import argparse

from ncluster import aws_util as u

parser = argparse.ArgumentParser(description='launch')
parser.add_argument('--replicas', type=int, default=1)
#parser.add_argument('--snapshot', type=str, default='imagenet18')
parser.add_argument('--snapshot', type=str, default='imagenet18-backup')
#parser.add_argument('--snapshot_account', type=str, default='316880547378',
#                    help='account id hosting this snapshot')

parser.add_argument('--volume_offset', type=int, default=0, help='start numbering with this value')
parser.add_argument('--size_gb', type=int, default=0, help="size in GBs")
parser.add_argument('--delete', action='store_true', help="delete volumes instead of creating")
parser.add_argument('--zone', default=None)

args = parser.parse_args()


def create_volume_tags(name):
    return [{
        'ResourceType': 'volume',
        'Tags': [{
            'Key': 'Name',
            'Value': name
        }]
    }]


# TODO: switch to snap-03e6fc1ab6d2da3c5

def main():
    ec2 = u.get_ec2_resource()
    if args.zone is None:
        zone = u.get_zone()
    else:
        zone = args.zone

    # use filtering by description since Name is not public
    # snapshots = list(ec2.snapshots.filter(Filters=[{'Name': 'description', 'Values': [args.snapshot]},
    #                                                {'Name': 'owner-id', 'Values': [args.snapshot_account]}]))

    snap = None
    if not args.delete:
        snapshots = list(ec2.snapshots.filter(Filters=[{'Name': 'description', 'Values': [args.snapshot]}]))

        assert len(snapshots) > 0, f"no snapshot matching {args.snapshot}"
        assert len(snapshots) < 2, f"multiple snapshots matching {args.snapshot}"
        snap = snapshots[0]
        if not args.size_gb:
            args.size_gb = snap.volume_size

    # list existing volumes
    vols = {}
    for vol in ec2.volumes.all():
        vols[u.get_name(vol)] = vol

    print(f"{'Deleting' if args.delete else 'Making'} {args.replicas} {args.size_gb} GB replicas in {zone}")

    for i in range(args.volume_offset, args.replicas + args.volume_offset):
        vol_name = f'imagenet_{zone[-2:]}_{i:02d}'
        if args.delete:
            print(f"Deleting {vol_name}")
            if vol_name not in vols:
                print("    Not found")
                continue
            else:
                try:
                    vols[vol_name].delete()
                except Exception as e:
                    print(f"Deletion of {vol_name} failed with {e}")
            continue

        if vol_name in vols:
            print(f"{vol_name} exists, skipping")
        else:
            vol = ec2.create_volume(Size=args.size_gb,
                                    TagSpecifications=create_volume_tags(vol_name),
                                    AvailabilityZone=zone,
                                    SnapshotId=snap.id,
                                    Iops=11500, VolumeType='io1')
            print(f"Creating {vol_name} {vol.id}")


if __name__ == '__main__':
    main()
