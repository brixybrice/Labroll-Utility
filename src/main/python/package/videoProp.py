from videoprops import get_video_properties

def getCodec(clip):
    props = get_video_properties(clip)
    codec = props['codec_name']
    #print(f'''
    #    Codec: {props['codec_name']}
    #    Resolution: {props['width']}×{props['height']}
    #    Aspect ratio: {props['display_aspect_ratio']}
    #    Frame rate: {props['avg_frame_rate']}
    #    ''')
    return codec

if __name__ == '__main__':

    clip = "/Users/bricebarbier/Dropbox/DAILYCIOUS/A001R89H/A001C002_20210220_R89H.mov"
    getCodec(clip=clip)