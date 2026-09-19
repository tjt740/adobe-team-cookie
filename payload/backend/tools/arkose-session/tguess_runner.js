/**
 * tguess generator - called from Python via subprocess
 * Usage: node tguess_runner.js <sessionToken> <guessJSON> <dapibScriptPath>
 * Output: JSON string of encrypted tguess {ct, iv, s}
 */
const vm = require("vm");
const crypto = require("crypto");
const fs = require("fs");

function encrypt(data, key) {
    let salt = "";
    let salted = "";
    let dx = Buffer.alloc(0);
    salt = String.fromCharCode(
        ...Array(8).fill(0).map(() => Math.floor(Math.random() * 26) + 97)
    );
    for (let x = 0; x < 3; x++) {
        dx = crypto.createHash("md5")
            .update(Buffer.concat([dx, Buffer.from(key), Buffer.from(salt)]))
            .digest();
        salted += dx.toString("hex");
    }
    let aes = crypto.createCipheriv(
        "aes-256-cbc",
        Buffer.from(salted.substring(0, 64), "hex"),
        Buffer.from(salted.substring(64, 96), "hex")
    );
    return JSON.stringify({
        ct: aes.update(data, undefined, "base64") + aes.final("base64"),
        iv: salted.substring(64, 96),
        s: Buffer.from(salt).toString("hex"),
    });
}

function generateTGuess(dapibScript, sessionToken, guess) {
    const [tokenKey, tokenValue] = sessionToken.split(".");
    const preparedGuess = guess.map(entry => ({
        ...entry,
        [tokenKey]: tokenValue,
    }));

    return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject("tguess timeout"), 5000);

        const dapibReceive = (data) => {
            clearTimeout(timeout);
            if (!data.tanswer) {
                return reject(`No tanswer: ${JSON.stringify(data)}`);
            }
            const tguess = data.tanswer.map(item =>
                Object.entries(item).reduce((obj, [key, value]) => {
                    obj[key] = value.slice(0, -1);
                    return obj;
                }, {})
            );
            resolve(encrypt(JSON.stringify(tguess), sessionToken));
        };

        const ctx = vm.createContext({
            window: {
                document: { hidden: false },
                parent: {
                    ae: {
                        dapibReceive,
                        answer: preparedGuess,
                    },
                },
            },
        });

        try {
            vm.runInContext(dapibScript, ctx, { timeout: 5000 });
        } catch (e) {
            clearTimeout(timeout);
            reject(`dapib exec error: ${e.message}`);
        }
    });
}

async function main() {
    const sessionToken = process.argv[2];
    const guessJSON = process.argv[3];
    const dapibPath = process.argv[4];

    if (!sessionToken || !guessJSON || !dapibPath) {
        console.error(JSON.stringify({ error: "Usage: node tguess_runner.js <sessionToken> <guessJSON> <dapibScriptPath>" }));
        process.exit(1);
    }

    const guess = JSON.parse(guessJSON);
    const dapibScript = fs.readFileSync(dapibPath, "utf-8");

    try {
        const result = await generateTGuess(dapibScript, sessionToken, guess);
        console.log(result);
    } catch (e) {
        console.error(JSON.stringify({ error: String(e) }));
        process.exit(1);
    }
}

main();
