from PySide6 import QtCore
import datetime, os, math
import cv2

from xml.dom import minidom
from xml.etree import ElementTree

standard_path = QtCore.QStandardPaths()
desktop_path = eval(f"standard_path.standardLocations(QtCore.QStandardPaths.DesktopLocation)")[0]


def exportXML(srcFilePath="", folder="dailycious_XML", scene="", shot="", incTakes=0):

    print("export XML")
    if incTakes == True:
        print("incrementing takes")
    # print(srcFilePath)

    def prettify(source):
        """ Return a pretty-printed XML string for the Element """
        rough_string = ElementTree.tostring(source, encoding="UTF-8", method="xml", short_empty_elements=False)
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="    ", newl="\n")

    def getCurrentDate():
        date = datetime.datetime.now()
        date_today = date.today()
        dateT = (str(date_today.year) + f'-{date_today.month:02d}' + f'-{date_today.day:02d}' + "T" + f'{date_today.hour}' + f':{date_today.minute:02d}' + f':{date_today.second:02d}')
        return dateT

    def frames_to_TC(frames, framerate):
        h = int(frames / (framerate*60*60))
        m = int(frames / (framerate*60)) % 60
        s = int((frames % (framerate*60)) / framerate)
        f = frames % (framerate*60) % framerate
        return ("%02d:%02d:%02d:%02d" % (h, m, s, f))
    # print(clip.timeCreation)

    class srcClip:
        def __init__(self, path, folder=folder):
            video = cv2.VideoCapture(path)
            self.path = path
            self.basename = os.path.basename(self.path)
            self.clipname = os.path.splitext(self.basename)[0]
            self.xmlPath = os.path.join(os.path.dirname(self.path), folder, self.clipname + ".xml")
            self.timeCreation = str(datetime.datetime.fromtimestamp(os.path.getmtime(path))).replace(" ", "T")

            framerate = video.get(cv2.CAP_PROP_FPS)
            self.framerate = str(framerate)

            frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            self.frames = str(frames)

            if frames < (framerate):
                self.duration = str(round(frames / framerate)) + " sec"

            elif frames < (framerate * 60) and frames > (framerate):
                self.duration = str(round(frames / framerate)) + " sec"

            elif frames < (framerate * 60 * 60) and frames > (framerate * 60):
                minutes = math.floor(frames / framerate / 60)
                secondes = math.floor((frames - (minutes * 60 * framerate)) / framerate)
                self.duration = str(minutes) + ":" + str(("%02d" % (secondes,))) + " min"
                print(self.duration)
                #self.duration = ("%02d:%02d min" % (str(minutes), str(secondes)))
            else:
                heures = math.floor(frames / framerate / 60 / 60)
                print(heures)
                minutes = math.floor((frames - (heures * 60 * 60 * framerate))/framerate/60)
                print(minutes)
                secondes = math.floor((frames - (heures * 60 * 60 * framerate) - (minutes * 60 * framerate)) / framerate)
                self.duration = str(heures) + ":" + str(("%02d" % (minutes,))) + ":" + str(("%02d" % (secondes,))) + " h"
                print(self.duration)

            self.StartTC = str(frames_to_TC(0, framerate))
            self.EndTC = str(frames_to_TC(frames, framerate))

    clip = srcClip(srcFilePath)

    main_content = ElementTree.Element('ClipReport')
    ElementTree.tostring(main_content, short_empty_elements=False)
    main_content.set("creationDate", getCurrentDate())
    main_content.set("version", "0.1")

    comment = ElementTree.Comment(' Dailycious XML ')
    main_content.append(comment)

    project = ElementTree.SubElement(main_content, 'Project')
    project.set("creationDate", getCurrentDate())


## PROJECT INFOS ##

    list_project_infos = ["Name",
                          "Cinematographer",
                          "DataWrangler",
                          "DigitalImageTechnician",
                          "Director",
                          "Location",
                          "Producer",
                          "Production"]

    for key in list_project_infos:
        elt = ElementTree.SubElement(project, key)
        if key not in srcFilePath:
            elt.text = "∏"
        else:
            elt.text = srcFilePath[ key ]
    
## BASE CLIP ##

    folder = ElementTree.SubElement(main_content, 'Folder')
    folder.set("creationDate", getCurrentDate())
    
    name = ElementTree.SubElement(folder, "Name")
    name.text = clip.clipname
    
    LibraryPath = ElementTree.SubElement(folder, "LibraryPath")
    LibraryPath.text = "∏"
    Content = ElementTree.SubElement(folder, "Content")

## ##

    VideoClip = ElementTree.SubElement(Content, "VideoClip")
    PosterPath = ElementTree.SubElement(VideoClip, "PosterPath")
    PosterPath.text = "∏"


## CLIP INFOS ##

    list_ClipInfos = ["Name", "Duration", "Frames", "FileCreationDate"]
    ClipInfo = ElementTree.SubElement(VideoClip, "ClipInfo")
    
    for key in list_ClipInfos:
        elt = ElementTree.SubElement(ClipInfo, key)
        if key == "FileCreationDate":
            elt.text = clip.timeCreation
        elif key == "Duration":
            elt.text = clip.duration
        elif key == "Name":
            elt.text = clip.clipname
        elif key == "Frames":
            elt.text = clip.frames


## SLATE INFOS ##

    list_SlateInfo = ["Episode", "Scene", "Shot", "Take", "Camera", "ShotDescriptors", "ShootingDate"]
    SlateInfo = ElementTree.SubElement(VideoClip, "SlateInfo")
    for key in list_SlateInfo:
        elt = ElementTree.SubElement(SlateInfo, key)
        elt.text = "∏"
        if key == "Scene":
            if scene is not "":
                elt.text = scene
            else:
                elt.text = clip.clipname
        elif key == "Shot":
            if shot is not "":
                elt.text = shot
            else:
                elt.text = "∏"
        elif key == "Take":
            if incTakes > 0:
                elt.text = str(incTakes)
            else:
                elt.text = "∏"
        elif key == "ShootingDate":
            elt.text = clip.timeCreation


## TIMECODE ##

    list_Timecode = ["StartTC", "EndTC", "FPSOfTC", "ReelTapeName"]
    Timecode = ElementTree.SubElement(VideoClip, "Timecode")
    for key in list_Timecode:
        elt = ElementTree.SubElement(Timecode, key)
        if key == "StartTC":
            elt.text = clip.StartTC
        elif key == "EndTC":
            elt.text = clip.EndTC
        elif key == "FPSOfTC":
            elt.text = clip.framerate
        elif key == "ReelTapeName":
            elt.text = clip.clipname

## USER INFOS ## 

    list_UserInfo = ["Flagged", "Rating", "Comment", "Label"]
    UserInfo = ElementTree.SubElement(VideoClip, "UserInfo")
    for key in list_UserInfo:
        elt = ElementTree.SubElement(UserInfo, key)
        if key == "Flagged":
            elt.text = "Flagged"
        else:
            elt.text = "∏"

## FORMAT ##

    list_Format = ["Codec", "FPS", "FileType", "Resolution"]
    Format = ElementTree.SubElement(VideoClip, "Format")
    for key in list_Format:
        elt = ElementTree.SubElement(Format, key)
        if key == "FPS":
            elt.text = clip.framerate
        else:
            elt.text = "∏"


## MISE EN PAGE ##

    characters_to_remove = "∏"
    XMLcontent = prettify(main_content)
    for character in characters_to_remove:
        XMLcontent = XMLcontent.replace(character, "")
    #print(XMLcontent)

## EXPORT & OPEN FILE ##

    destination = os.path.dirname(clip.xmlPath)
    
    if not os.path.exists(destination):
        os.makedirs(destination)

    with open(clip.xmlPath, 'w') as the_file:
        the_file.write(XMLcontent)

    return os.path.exists(clip.xmlPath)
    #subprocess.Popen(["open", "-R", destination])



#####    SCRIPT PYTHON TESTING  #####

if __name__ == '__main__':

    srcFilePath = "/Users/bricebarbier/Dropbox/DAILYCIOUS/A001R89H/A001C002_20210220_R89H.mov"
    exportXML(srcFilePath=srcFilePath)


