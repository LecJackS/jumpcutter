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

### Main diffs to Carykh project:

* Frame rate is now a parameter as "auto discover frame rate" does not work

* Added silent_threshold_abs parameter as silent threshold with absolute value (not percent of max volume). Good for videos recorded in similar conditions.

* Added noise reduction to the end video file:
  https://github.com/LecJackS/jumpcutter/commit/ff075e83085885b53a513c8d454f0d4c769547c5#diff-c7086a2be3661ab78f759ef1da70ed6394a89ec8883b54b704c5f72218b835e8R102

---

Original work: https://github.com/carykh/jumpcutter

---

Automatically edits videos. Explanation here: https://www.youtube.com/watch?v=DQ8orIurGxw

## Some heads-up:

It uses Python 3.

It works on Ubuntu <= 20.04 and Windows 10. (It might work on other OSs too, we just haven't tested it yet.)

This program relies heavily on ffmpeg. It will start subprocesses that call ffmpeg, so be aware of that!

As the program runs, it saves **every** frame of the video as an image file in a temporary folder.

If your video is long, this could take a LOT of space (several GB)

I have processed ~1 hour videos completely fine, but be wary if you're gonna go longer.

---

## Building with nix
`nix-build` to get a script with all the libraries and ffmpeg, `nix-build -A bundle` to get a single binary.
