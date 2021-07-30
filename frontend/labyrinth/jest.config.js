module.exports = {
    preset: "@vue/cli-plugin-unit-jest",
    "collectCoverage": true,
    "collectCoverageFrom": ["**/*.{js,vue}", "!**/node_modules/**"],
    "coverageThreshold": {
        "global" : {
            "lines" : 90
        }
    }
};
