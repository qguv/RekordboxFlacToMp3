import xml.etree.ElementTree as ET
import os
import copy
import argparse
import subprocess
from urllib.parse import quote, unquote
import sys
import pathlib

CONVERTED_PLAYLIST_SUFFIX = '_MP3'


def from_rekordbox_path(s):
    assert s.startswith('file://localhost'), f"unrecognized path {s}!"
    s = s[16:]

    # strip leading slash on windows
    if s[2] == ':':
        s = s[1:]

    return unquote(s)


def to_rekordbox_path(s):

    # add leading slash on windows
    if s[1] == ':':
        s = '/' + s

    return 'file://localhost' + quote(s)


class NoConversionNeeded(Exception):
    pass


class Collection:
    def __init__(self, node):
        self.node = node
        self.tracks_by_location = {from_rekordbox_path(track.get('Location')): track for track in self.node}

    def get_largest_trackid(self):
        return max(int(track.get('TrackID')) for track in self.node)

    def get_track(self, trackid):
        node = self.node.find(f"TRACK[@TrackID='{trackid}']")
        assert node is not None
        return node

    def get_converted(self, node):
        assert(node is not None)
        location = from_rekordbox_path(node.get('Location'))
        if not location.endswith('.flac'):
            raise NoConversionNeeded()
        converted_location = location[:-5] + '.mp3'
        try:
            return self.tracks_by_location[converted_location]
        except KeyError:
            if pathlib.Path(converted_location).exists():
                print("using existing mp3", file=sys.stderr)
            else:
                ffmpegFLAC2MP3(location, converted_location)
            new_node = copy.deepcopy(node)
            new_node.set('Location', to_rekordbox_path(converted_location))
            new_node.set('TrackID', str(self.get_largest_trackid() + 1))
            self.node.append(new_node)
            self.node.set('Entries', str(int(self.node.get('Entries')) + 1))
            return new_node


class Playlist:
    def __init__(self, node, ancestors, collection):
        assert(str(node.get('Type')) == "1")

        self.node = node
        self.ancestors = ancestors
        self.collection = collection

        self.name = self.node.get('Name')
        assert(not self.name.endswith(CONVERTED_PLAYLIST_SUFFIX))

        self.tracks = list(self._get_tracks())


    def _get_tracks(self):
        for track_ref in self.node:
            assert(track_ref.tag == 'TRACK')
            trackid = track_ref.get('Key')
            print(f"looking for track {trackid}", file=sys.stderr)
            yield self.collection.get_track(trackid)

    def convert(self):
        assert(not self.name.endswith(CONVERTED_PLAYLIST_SUFFIX))
        newname = self.name + CONVERTED_PLAYLIST_SUFFIX

        # find self in parent
        parent = self.ancestors[-1]
        i = list(parent).index(self.node)

        # if already converted, delete
        if i + 1 < len(parent) and parent[i+1].get('Name') == newname:
            print("re-creating playlist", newname, file=sys.stderr)
            parent.remove(parent[i+1])
            parent.set('Count', str(int(parent.get('Count')) - 1))

        converted = copy.deepcopy(self.node)
        converted.set('Name', newname)
        for track_ref_node in converted:
            old_track_node = self.collection.get_track(track_ref_node.get('Key'))
            try:
                new_track_node = self.collection.get_converted(old_track_node)
            except NoConversionNeeded:
                continue
            track_ref_node.set('Key', new_track_node.get('TrackID'))
        parent.insert(i+1, converted)
        parent.set('Count', str(int(parent.get('Count')) + 1))

    @classmethod
    def get_originals(cls, node, collection, ancestors=tuple()):
        assert(str(node.get('Type')) == '0')
        for child in node:

            # recurse on collections
            if str(child.get('Type')) == '0':
                yield from cls.get_originals(child, collection, ancestors=(*ancestors, node))
                continue

            # skip converted playlists
            if child.get('Name').endswith(CONVERTED_PLAYLIST_SUFFIX):
                continue

            yield cls(child, (*ancestors, node), collection)

    def __repr__(self):
        s = ' -> '.join(x.get('Name') for x in (*self.ancestors, self.node)[1:])
        s = f'<Playlist: {s}>'
        return s


'''
def get_playlist_node(playlists_tree, path):
    searchStr = '/'.join(f"NODE[@Name='{p}']" for p in path)
    return playlists_tree.find(searchStr)
'''


def convert(REKORDBOX_XML, NEW_XML, only_playlist=None):
    xmlFile = ET.parse(REKORDBOX_XML)
    root_node = xmlFile.getroot()
    collection = Collection(root_node[1])
    playlists = list(Playlist.get_originals(root_node[2][0], collection))
    for playlist in playlists:
        name = playlist.node.get('Name')
        if only_playlist is None or only_playlist == name:
            print("converting playlist", playlist.node.get('Name'), file=sys.stderr)
            playlist.convert()
    xmlFile.write(NEW_XML)

'''
    # track id at which to add a new track. Amount of existing entries +1. Incremented every new track created
    currId = int(collection.get('Entries')) + 1
    for track in collection:
        rawPath = track.get('Location')

        # skip file if not a flac
        if not rawPath.lower().endswith('.flac'):
            continue

        # get path in python parseable format
        flacPath = from_rekordbox_path(rawPath)

        # get the original track id to figure out what playlists the new mp3 will need to be added to
        # don't convert if it isn't in any playlists to save time
        inPlaylist = False
        origId = track.get('TrackID')
        for pl in pNodes:

            searchStr = "*/[@Key='" + origId + "']"
            result = pl.findall(searchStr)
            if result == []:
                continue
            inPlaylist = True
            pname = pl.get('Name')
            print('Found track {} in playlist {}'.format(origId, pname))
            # find the mp3 version of the playlist and append the new mp3 id to it
            mp3listName = pname + CONVERTED_PLAYLIST_SUFFIX
            searchStr = "*/[@Name='" + mp3listName + "']"
            mp3list = playlists.find(searchStr)
            newTrack = ET.SubElement(mp3list, 'TRACK')
            newTrack.set('Key', str(currId))
        if not inPlaylist:
            continue
        # at this point, the file was found in at least one playlist
        # convert the file if mp3 doesn't exist already
        mp3Path = flacPath[:-5] + '.mp3'

        if os.path.exists(mp3Path):
            print(f"===\nskipping {mp3Path} (file exists)\n===\n\n")
        else:
            # convert the flac to a 320 kpbs mp3
            ffmpegFLAC2MP3(flacPath, mp3Path)

        # copy the old xml track entry and modify the necessary fields
        newTrack = copy.deepcopy(track)
        newTrack.set('TrackID', str(currId))
        newTrack.set('Location', to_rekordbox_path(mp3Path))
        newTrack.set('Kind', "MP3 File")
        newTrack.set('BitRate', "320")
        collection.append(newTrack)
        # increment the current song id number
        currId += 1
    collection.set('Entries', str(currId-1))
    '''


# convert FLAC at inFlac path to 320 kpbs mp3 at outmp3 path
def ffmpegFLAC2MP3(inFlac, outmp3):
    try:
        subprocess.check_call([
                  "ffmpeg",
                  "-i", inFlac,
                  "-ab", "320k",
                  "-map_metadata", "0",
                  "-id3v2_version", "3",
                  outmp3,
                  "-nostdin",
        ])
    except subprocess.CalledProcessError:
        print(f'removing {outmp3}', file=sys.stderr)
        pathlib.Path(outmp3).unlink()
        sys.exit(16)
    except KeyboardInterrupt:
        print('interrupted', file=sys.stderr)
        print(f'removing {outmp3}', file=sys.stderr)
        pathlib.Path(outmp3).unlink()
        sys.exit(16)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
            '--input', '-i',
            type=argparse.FileType('rb'),
            default='-',
            help="old Rekordbox library XML export",
    )
    parser.add_argument(
            '--output','-o',
            type=argparse.FileType('wb'),
            default='-',
            help="location to write converted Rekordbox library XML",
    )
    parser.add_argument(
            '--playlist','-p',
            help="which playlist to convert",
    )


    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    convert(args.input, args.output, only_playlist=args.playlist)
