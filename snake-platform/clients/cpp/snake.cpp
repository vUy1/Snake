// The C++ skeleton for the course text protocol: read the state, print a move.
//
//   g++ -O2 -std=c++17 -o mysnake snake.cpp
//   python -m snake.cli play "cmd:./mysnake" survivor hungry wander --seed 1
//
// Do not call the binary `snake` - there is already a `snake/` folder here.
// See docs/protocol.md for the wire format, including the wrapping rule.

#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <random>

struct Cell { int x, y; };

// "10,12 15,12" -> {{10,12},{15,12}}. A point repeated twice is a teleport
// through the edge of the board - see docs/protocol.md.
static std::vector<Cell> parseCells(const std::string& line) {
    std::vector<Cell> cells;
    std::istringstream in(line);
    std::string token;
    while (in >> token) {
        auto comma = token.find(',');
        if (comma == std::string::npos) continue;
        cells.push_back({std::stoi(token.substr(0, comma)), std::stoi(token.substr(comma + 1))});
    }
    return cells;
}

// Anything you want to read later; it goes to the log file, not to the game.
static void logLine(const std::string& message) {
    std::cout << "log " << message << std::endl;
}

int main() {
    std::string line;
    if (!std::getline(std::cin, line)) return 0;

    int snakeCount, width, height, mode;
    std::istringstream(line) >> snakeCount >> width >> height >> mode;

    std::mt19937 rng(12345);
    bool seeded = false;

    while (std::getline(std::cin, line)) {
        if (line == "Game Over") return 0;       // you have ~500ms here
        if (line.empty()) continue;

        int appleX, appleY;
        std::istringstream(line) >> appleX >> appleY;
        if (!seeded) { rng.seed(std::hash<std::string>{}(line)); seeded = true; }

        std::string meLine;
        std::getline(std::cin, meLine);
        int me = std::stoi(meLine);

        std::vector<std::string> snakes(snakeCount);
        for (int i = 0; i < snakeCount; ++i) std::getline(std::cin, snakes[i]);

        // Your own line: "alive <length> <kills> <chain...>".
        std::istringstream mine(snakes[me]);
        std::string status; int length, kills;
        mine >> status >> length >> kills;
        std::string rest, token;
        while (mine >> token) rest += token + " ";
        std::vector<Cell> myChain = parseCells(rest);

        // Replace this. 0 up, 1 down, 2 left, 3 right;
        //               4 left, 5 straight, 6 right, relative to your head.
        std::cout << (rng() % 4) << std::endl;
    }
    return 0;
}
