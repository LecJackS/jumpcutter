# jumpcutter - Automatically pop silences from videos

Add this to `~/.bashrc` to run the script in any directory as `jcc some-video.mp4 some-other-video.mkv`

Remove `cd ~/Videos` in case you don't need that.

```bash
# Video silence cutter
jcc (){
    cd ~/Videos;
    for file_name in "$@"
    do
        python ~/jumpcutter/jumpcutter.py --silent_speed 999999 --frame_margin 8 --frame_quality 3 --frame_rate 25 --silent_threshold 0.06 --input_file $file_name
    done
}
```


---

Original work from: carykh

Automatically edits videos. Explanation here: https://www.youtube.com/watch?v=DQ8orIurGxw

## Some heads-up:

It uses Python 3.

It works on Ubuntu 16.04 and Windows 10. (It might work on other OSs too, we just haven't tested it yet.)

This program relies heavily on ffmpeg. It will start subprocesses that call ffmpeg, so be aware of that!

As the program runs, it saves every frame of the video as an image file in a
temporary folder. If your video is long, this could take a LOT of space.
I have processed 17-minute videos completely fine, but be wary if you're gonna go longer.

I want to use pyinstaller to turn this into an executable, so non-techy people
can use it EVEN IF they don't have Python and all those libraries. Jabrils 
recommended this to me. However, my pyinstaller build did not work. :( HELP

## Building with nix
`nix-build` to get a script with all the libraries and ffmpeg, `nix-build -A bundle` to get a single binary.
