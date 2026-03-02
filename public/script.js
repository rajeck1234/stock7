const API = "https://stock7-production-ffb1.up.railway.app/";
// const API = "https://stock5-production.up.railway.app/";

let coun = 0;
const alarm = new Audio("alarm.mp3");
let alertStocks = [];

let coun1 = 0;
let coun2 = 0;
let totalOrders = 0;
let totalProfit = 0;
let removedStrongSignal = [];
let removedStableGrowth = [];
let removedMomentum = [];

let upInterval = null;
let downInterval = null;
let removedStartMovement = [];

let upActive = false;
let downActive = false;
/* ================= COPY FUNCTION ================= */
function copyName(fullName) {
    const cleanName = fullName.replace(".NS", "");
    navigator.clipboard.writeText(cleanName)
        .then(() => alert("Copied: " + cleanName))
        .catch(err => console.error("Copy failed", err));
}

/* ================= LOAD STOCKS ================= */
async function loadStocks() {

    coun++;

    const res = await fetch(API + "/stocks");
    const data = await res.json();

    const div = document.getElementById("stocks");
    div.innerHTML = "";

    data.forEach(stock => {

        div.innerHTML += `
        <div class="stock">
            <h3>${stock.name}</h3>
            <p>Price: ₹${stock.price ?? 0}</p>
            <button onclick="copyName('${stock.name}')">Copy</button>
            <button class="buy" onclick="buyStock('${stock.name}', ${stock.price})">Buy</button>
            <button onclick="removeStock('${stock.name}')">Remove</button>
        </div>
        `;
    });
}

/* ================= ALERT SECTION ================= */
async function checkAlerts() {

    const res = await fetch(API + "/check-alerts");
    const data = await res.json();

    alertStocks = data;
    loadPortfolio();

    if (data.length > 0) {
        alarm.play();
        document.getElementById("stopAlarm").style.display = "block";
    }
}

async function addStock() {

    let symbol = prompt("Enter Stock Symbol (Example: HCLTECH)");
    if (!symbol) return;

    await fetch(API + "/add-stock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol })
    });

    loadStocks();
}

async function removeStock(name){
    await fetch(API + "/removeStock/" + name,{ method:"DELETE" });
    loadStocks();
}

/* ================= PORTFOLIO ================= */
async function loadPortfolio() {

    const res = await fetch(API + "/portfolio");
    const data = await res.json();

    const div = document.getElementById("portfolio");
    div.innerHTML = "";

    data.forEach(stock => {

        const isAlert = alertStocks.includes(stock.name);

        div.innerHTML += `
        <div class="stock ${isAlert ? "alert-stock" : ""}">
            <h3>${stock.name}</h3>
            <p>Bought At: ₹${stock.buy_price ?? 0}</p>
            <button onclick="sellStock('${stock.name}')"
                class="${isAlert ? "sell-alert" : ""}">
                Sell
            </button>
        </div>
        `;
    });
}

/* ================= BUY (AUTO PRICE) ================= */
async function buyStock(name, price) {

    if (!price) {
        alert("Price not available");
        return;
    }

    await fetch(API + "/add-stock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: name.replace(".NS","") })
    });

    await fetch(API + "/buy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, price })
    });

    loadStocks();
    loadPortfolio();
}

/* ================= SELL ================= */
function stopAlarm() {
    alarm.pause();
    alarm.currentTime = 0;
    document.getElementById("stopAlarm").style.display = "none";
}

async function sellStock(name) {

    // Get portfolio first to calculate profit
    const res = await fetch(API + "/portfolio");
    const data = await res.json();

    const stock = data.find(s => s.name === name);

    if (stock) {

        const currentPriceRes = await fetch(API + "/stocks");
        const stocksData = await currentPriceRes.json();
        const currentStock = stocksData.find(s => s.name === name);
        // console.log("buy");
        // console.log(currentStock);
        // console.log("sell");
        // console.log(stock.buy_price);

        if (currentStock) {
            const profit = (currentStock.price ?? 0) - (stock.buy_price ?? 0);
            totalProfit += profit;
            totalOrders += 1;
            updateTradeSummary();
        }
    }

    await fetch(API + "/sell", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
    });

    loadPortfolio();
}

function updateTradeSummary() {
    document.getElementById("tradeSummary").innerText =
        `Orders: ${totalOrders} | Profit: ₹${totalProfit.toFixed(2)}`;
}


/* ================= MOMENTUM 5 SEC % ================= */
async function loadMomentum30() {

    const res = await fetch("/momentum30");
    const data = await res.json();

    const container = document.getElementById("momentum30");
    container.innerHTML = "";

    let count = 0;

    data.forEach(stock => {

        if (removedMomentum.includes(stock.name)) return;
        if (count >= 5) return;

        container.innerHTML += `
        <div class="stock">
            <div style="flex:1;">
                ${stock.name}
                ₹${(stock.price ?? 0).toFixed(2)}
                (${Number(stock.change ?? 0).toFixed(2)}%)
            </div>
            <button onclick="copyName('${stock.name}')">Copy</button>
            <button class="buy" onclick="buyStock('${stock.name}', ${stock.price})">Buy</button>
            <button onclick="removeFromMomentum('${stock.name}')">Remove</button>
        </div>
        `;
        count++;
    });

    loadRemovedMomentumBox();
}

/* ================= MOMENTUM 10 SEC % ================= */
async function loadMomentum3() {

    const res = await fetch("/momentum3min");
    const data = await res.json();

    const container = document.getElementById("momentum3");
    container.innerHTML = "";

    let count = 0;

    data.forEach(stock => {

        if (removedMomentum.includes(stock.name)) return;
        if (count >= 5) return;

        container.innerHTML += `
        <div class="stock">
            <div style="flex:1;">
                ${stock.name}
                ₹${(stock.price ?? 0).toFixed(2)}
                (${Number(stock.change ?? 0).toFixed(2)}%)
            </div>
            <button onclick="copyName('${stock.name}')">Copy</button>
            <button class="buy" onclick="buyStock('${stock.name}', ${stock.price})">Buy</button>
            <button onclick="removeFromMomentum('${stock.name}')">Remove</button>
        </div>
        `;
        count++;
    });

    loadRemovedMomentumBox();
}

/* ================= MOMENTUM 5 SEC PRICE ================= */
async function loadMomentum30Price(){

    const res = await fetch(API + "/momentum30price");
    const data = await res.json();

    const div = document.getElementById("momentum30price");
    div.innerHTML = "";

    let count = 0;

    data.forEach(stock=>{

        if (removedMomentum.includes(stock.name)) return;
        if (count >= 5) return;

        div.innerHTML += `
        <div class="stock">
            <div style="flex:1;">
                <b>${stock.name}</b>
                ₹${stock.price ?? 0}
                +₹${stock.change ?? 0}
            </div>
            <button onclick="copyName('${stock.name}')">Copy</button>
            <button class="buy" onclick="buyStock('${stock.name}', ${stock.price})">Buy</button>
            <button onclick="removeFromMomentum('${stock.name}')">Remove</button>
        </div>
        `;
        count++;
    });

    loadRemovedMomentumBox();
}
/* ================= MOMENTUM 1 MIN LOSS ================= */
async function loadMomentum1Loss() {

    const res = await fetch(API + "/momentum1loss");
    const data = await res.json();
    
    const div = document.getElementById("momentum1loss");
    div.innerHTML = "";

    let count = 0;

    for (const stock of data) {

        if (removedMomentum.includes(stock.name)) continue;
        if (count >= 5) break;

        const name = stock.name;
        const price = stock.price;
        const change = stock.change;

        div.innerHTML += `
        <div class="stock">
            <div style="flex:1;">
                <b>${name}</b>
                ₹${Number(price).toFixed(2)}
                <span style="color:red;">
                    (${Number(change).toFixed(2)}%)
                </span>
            </div>
            <button onclick="copyName('${name}')">Copy</button>
            <button class="buy" onclick="buyStock('${name}', ${price})">Buy</button>
            <button onclick="removeFromMomentum('${name}')">Remove</button>
        </div>
        `;
        count++;
    }

    loadRemovedMomentumBox();
}
function removeFromMomentum(name){
    if(!removedMomentum.includes(name)){
        removedMomentum.push(name);
    }
}

function addBackMomentum(name){
    removedMomentum =
        removedMomentum.filter(s=>s!==name);
}

function loadRemovedMomentumBox(){

    const div =
        document.getElementById("removedMomentumBox");

    if(!div) return;

    div.innerHTML = "";

    removedMomentum.forEach(name=>{
        div.innerHTML += `
        <div class="stock">
            <div style="flex:1;">${name}</div>
            <button class="buy"
                onclick="addBackMomentum('${name}')">
                Add
            </button>
        </div>
        `;
    });
}


async function loadMomentum3Price(){

    const res = await fetch(API + "/momentum3minprice");
    const data = await res.json();

    const div = document.getElementById("momentum3price");
    div.innerHTML = "";

    let count = 0;

    for (const name in data) {

        if(removedStrongSignal.includes(name)) continue;

        if(count >= 5) break;   // 👈 always show only 5

        const price = data[name].price;
        const change = data[name].change;

        div.innerHTML += `
        <div class="stock">
            <div style="flex:1;">
                <b>${name}</b>
                ₹${Number(price).toFixed(2)}
                <span style="color:${change >= 0 ? 'lime' : 'red'}">
                    (${Number(change).toFixed(2)}%)
                </span>
            </div>

            <button onclick="copyName('${name}')">Copy</button>
            <button class="buy"
                onclick="buyStock('${name}', ${price})">
                Buy
            </button>
            <button onclick="removeFromStrong('${name}')">
                Remove
            </button>
        </div>
        `;

        count++;
    }

    loadRemovedStrongBox();
}

async function loadStableGrowth(){

    const res = await fetch(API + "/stablegrowth");
    const data = await res.json();

    const div = document.getElementById("stablegrowth");
    div.innerHTML = "";

    let count = 0;

    data.forEach(stock => {

        if(removedStableGrowth.includes(stock.name)) return;

        if(count >= 5) return;   // 👈 THIS LINE IS IMPORTANT

        div.innerHTML += `
        <div class="stock">
            <div style="flex:1;">
                <b>${stock.name}</b>
                ₹${Number(stock.price).toFixed(2)}
                <span style="color:lime;">
                    Trend: ${stock.overall_change}% | Stable: ${stock.fluctuation}
                </span>
            </div>

            <button onclick="copyName('${stock.name}')">Copy</button>
            <button class="buy"
                onclick="buyStock('${stock.name}', ${stock.price})">
                Buy
            </button>
            <button onclick="removeFromStable('${stock.name}')">
                Remove
            </button>
        </div>
        `;

        count++;   // 👈 increment counter
    });

    loadRemovedStableBox();
}

function loadRemovedStrongBox(){

    const div =
        document.getElementById("removedStrongBox");
    div.innerHTML = "";

    removedStrongSignal.forEach(name=>{
        div.innerHTML += `
        <div class="stock">
            <div style="flex:1;">${name}</div>
            <button class="buy"
                onclick="addBackStrong('${name}')">
                Add
            </button>
        </div>
        `;
    });
}

function loadRemovedStableBox(){

    const div =
        document.getElementById("removedStableBox");
    div.innerHTML = "";

    removedStableGrowth.forEach(name=>{
        div.innerHTML += `
        <div class="stock">
            <div style="flex:1;">${name}</div>
            <button class="buy"
                onclick="addBackStable('${name}')">
                Add
            </button>
        </div>
        `;
    });
}

function toggleStartMovement(direction){

    if(direction === "up"){

        if(upActive){
            upActive = false;
            clearInterval(upInterval);
            upInterval = null;
            document.getElementById("startMovementContainerUp").innerHTML = "";
            return;
        }

        upActive = true;
        loadStartMovement("up");
        upInterval = setInterval(() => {
            if(upActive){
                loadStartMovement("up");
            }
        }, 1000);
    }

    if(direction === "down"){

        if(downActive){
            downActive = false;
            clearInterval(downInterval);
            downInterval = null;
            document.getElementById("startMovementContainerDown").innerHTML = "";
            return;
        }

        downActive = true;
        loadStartMovement("down");
        downInterval = setInterval(() => {
            if(downActive){
                loadStartMovement("down");
            }
        }, 1000);
    }
}



async function loadStartMovement(direction){
    if(direction === "up" && !upActive) return;
    if(direction === "down" && !downActive) return;
    const res = await fetch(API + "/start-movement/" + direction);
    const data = await res.json();

    const containerId =
        direction === "up"
        ? "startMovementContainerUp"
        : "startMovementContainerDown";

    const div = document.getElementById(containerId);
    div.innerHTML = "";

    let count = 0;

    data.forEach(stock => {

        if(removedStartMovement.includes(stock.name)) return;
        if(count >= 5) return;

        div.innerHTML += `
        <div class="stock">
            <div style="flex:1;">
                <b>${stock.name}</b>
                Start: ₹${Number(stock.start_price).toFixed(2)}
                Current: ₹${Number(stock.current_price).toFixed(2)}
                <span style="color:${stock.change >= 0 ? 'lime' : 'red'}">
                    (${Number(stock.change).toFixed(2)}%)
                </span>
            </div>

            <button onclick="copyName('${stock.name}')">Copy</button>
            <button class="buy"
                onclick="buyStock('${stock.name}', ${stock.current_price})">
                Buy
            </button>
            <button onclick="removeFromStartMovement('${stock.name}')">
                Remove
            </button>
        </div>
        `;

        count++;
    });

    loadRemovedStartMovementBox();
}

function removeFromStartMovement(name){
    if(!removedStartMovement.includes(name)){
        removedStartMovement.push(name);
    }
}

function addBackStartMovement(name){
    removedStartMovement =
        removedStartMovement.filter(s=>s!==name);
}

function loadRemovedStartMovementBox(){

    const div =
        document.getElementById("removedStartMovementBox");

    if(!div) return;

    div.innerHTML = "";

    removedStartMovement.forEach(name=>{
        div.innerHTML += `
        <div class="stock">
            <div style="flex:1;">${name}</div>
            <button class="buy"
                onclick="addBackStartMovement('${name}')">
                Add
            </button>
        </div>
        `;
    });
}

function removeFromStrong(name){
    if(!removedStrongSignal.includes(name)){
        removedStrongSignal.push(name);
    }
}

function removeFromStable(name){
    if(!removedStableGrowth.includes(name)){
        removedStableGrowth.push(name);
    }
}

function addBackStrong(name){
    removedStrongSignal =
        removedStrongSignal.filter(s=>s!==name);
}

function addBackStable(name){
    removedStableGrowth =
        removedStableGrowth.filter(s=>s!==name);
}


setInterval(loadStableGrowth, 1000);
loadStableGrowth();

/* ================= INTERVALS ================= */
setInterval(loadMomentum30Price,1000);
setInterval(loadMomentum3Price,1000);
setInterval(loadMomentum30,1000);
setInterval(loadMomentum3,1000);
setInterval(loadStocks, 1000);
setInterval(checkAlerts, 1000);
setInterval(loadMomentum1Loss,1000);
// setInterval(loadStartMovement,1000);

// loadStartMovement();
loadMomentum1Loss();

loadMomentum30();
loadMomentum3();
loadStocks();
loadPortfolio();
loadMomentum30Price();
loadMomentum3Price();
