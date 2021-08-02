module.exports = {
    preset: "@vue/cli-plugin-unit-jest",
    "collectCoverage": true,
    "collectCoverageFrom": ["**/*.vue", "src/helper.js", "!**/node_modules/**"],
    "coverageThreshold": {
        "global" : {
            "lines" : 90
        }
    }
};
