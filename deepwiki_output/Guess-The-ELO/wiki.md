# Wiki Documentation for https://github.com/hieuimba/Guess-The-ELO

Generated on: 2025-06-15 19:46:25

## Table of Contents

- [Full Codebase Overview](#all-files-57c345ad-c2e6-41fe-8f22-e590fd166a2e)

<a id='all-files-57c345ad-c2e6-41fe-8f22-e590fd166a2e'></a>

## Full Codebase Overview

# Guess The ELO Codebase Wiki

## Overview

"Guess The ELO" is a web-based game that challenges players to guess the Elo rating of chess matches. It uses data from Lichess to provide a diverse and up-to-date gaming experience. The codebase is structured to support both gameplay and user interface elements, with resources for sound effects, images, and game logic.

## File Structure

### Configuration and Metadata

- **.github/workflows/deploy-to-itch.yml**: Contains GitHub Actions workflow for deploying the project to itch.io.
- **.gitignore**: Specifies files and directories to be ignored by Git.
- **.nojekyll**: Disables Jekyll processing on GitHub Pages.
- **CNAME**: Contains the custom domain name for the GitHub Pages site.

### Documentation

- **README.md**: Provides an overview of the game, features, how to play, and data sources.

### Styles and Assets

- **css/styles.css**: Contains styles for the game's user interface, including layout, colors, and animations.
- **favicon.ico**: The favicon for the website.
- **images/**: Directory containing various images used in the game, such as annotate icons, background, and mini chess pieces.
  - **annotate-icons/**: SVG icons for different types of chess moves (blunder, inaccuracy, mistake).
  - **background-pc.png**: Background image for the game.
  - **icons/**: Icons for game status (fire, heart).
  - **mini-pieces/**: Miniature SVG representations of chess pieces.
- **sounds/**: Directory containing sound effects and background music for the game.
  - **effects/**: Sound effects for game interactions (correct, incorrect, countdown, game start/end).
  - **music.mp3**: Background music for the game.

### HTML and JavaScript

- **index.html**: The main HTML file for the game, setting up the basic structure and linking to styles and scripts.
- **js/**: Directory containing JavaScript files for game logic and UI elements.
  - **data/fetchGames.js**: Responsible for fetching chess games data.
  - **elements/**: Scripts for specific UI components.
    - **chessBoard.js**: Handles chessboard display and interactions.
    - **clock.js**: Manages game clock functionality.
    - **modal.js**: Manages modal dialog interactions.
  - **game.js**: Main game logic, including game setup and event handling.
  - **home.js**: Handles the home screen and game mode selections.
  - **other/**: Utility scripts for configuration and UI adjustments.
    - **config.js**: Contains configuration settings.
    - **resize.js**: Handles responsive resizing of UI elements.
    - **utils.js**: General utility functions used across the codebase.

### Sitemap

- **sitemap.xml**: Sitemap for the website, aiding search engines in indexing the site.

## Features

- **Game Modes**: Classic and Endless modes with varying challenges.
- **Responsive Design**: Adaptable to both desktop and mobile devices.
- **Interactive UI**: Includes sound effects, animations, and dynamic content updates.

## Development and Deployment

The project uses GitHub for version control and continuous deployment to itch.io, allowing for easy updates and maintenance. The codebase is structured to facilitate easy navigation and modification, with clear separation of concerns between different components.

---
