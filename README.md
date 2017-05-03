![Monkey-Logo](https://raw.githubusercontent.com/nzblnk/nzb-monkey/master/resource/nzb-monkey-128.png)

# NZB Monkey

Reference implementation of how to handle a [NZBLNK](https://nzblnk.github.io/)-URI.

## Runing the monkey

See detailed information [here](https://nzblnk.github.io/nzb-monkey/).

## Build the windows binary

Use a **32-bit python v3.4** and install all requirements:

`pip install -r requirements-build.txt `

To build the EXE just call:

`make_windows.cmd`

## Contribution

Feel free to send pull requests.

### macOS Support

To run nzbmonkey on OSX follow this recipe:

- brew install python3
- checkout the source (~/Source/nzb-monkey in my case)
- download LinCastor here: https://onflapp.wordpress.com/lincastor/ and install
- setup a new url-scheme as shown in my screenshot (see resource/Lincastor.png)

This approach still has two problems:

- the terminal window doesn't close automatically
- then debugging is enabled an error is generated and the monkey doesn't work :(
