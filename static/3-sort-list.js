function slist(target) {
    // (A) SET CSS + GET ALL LIST ITEMS
    target.classList.add("slist");
    let items = target.getElementsByTagName("li"),
        current = null;

    // (B) MAKE ITEMS DRAGGABLE + SORTABLE
    for (let i of items) {
        // (B1) ATTACH DRAGGABLE
        i.draggable = true;

        // (B2) DRAG START - YELLOW HIGHLIGHT DROPZONES
        i.ondragstart = (e) => {
            current = i;
            for (let it of items) {
                if (it != current) {
                    it.classList.add("hint");
                }
            }
        };

        // (B3) DRAG ENTER - RED HIGHLIGHT DROPZONE
        i.ondragenter = (e) => {
            if (i != current) {
                i.classList.add("active");
            }
        };

        // (B4) DRAG LEAVE - REMOVE RED HIGHLIGHT
        i.ondragleave = () => i.classList.remove("active");

        // (B5) DRAG END - REMOVE ALL HIGHLIGHTS
        i.ondragend = () => {
            for (let it of items) {
                it.classList.remove("hint");
                it.classList.remove("active");
            }
        };

        // (B6) DRAG OVER - PREVENT THE DEFAULT "DROP", SO WE CAN DO OUR OWN
        i.ondragover = (e) => e.preventDefault();

        // (B7) ON DROP - DO SOMETHING
        i.ondrop = (e) => {
            e.preventDefault();
            if (i != current) {
                let currentpos = 0,
                    droppedpos = 0;
                for (let it = 0; it < items.length; it++) {
                    if (current == items[it]) {
                        currentpos = it;
                    }
                    if (i == items[it]) {
                        droppedpos = it;
                    }
                }
                if (currentpos < droppedpos) {
                    i.parentNode.insertBefore(current, i.nextSibling);
                } else {
                    i.parentNode.insertBefore(current, i);
                }
            }
        };
    }
}
// get guild name from url args
const urlParams = new URLSearchParams(window.location.search);
const guild = urlParams.get("guild");
function fetchData() {
    fetch("/get_data?guild=" + guild)
        .then((response) => response.json())
        .then((data) => {
            const playlist = data.playlist;
            const pllength = data.pllength;
            const sortlist = document.getElementById("sortlist");
            sortlist.innerHTML = ""; // Clear the existing list

            playlist.forEach((song, index) => {
                const li = document.createElement("li");
                const img = document.createElement("img");
                const div1 = document.createElement("div");
                const div2 = document.createElement("div");
                const div3 = document.createElement("div");
                const div4 = document.createElement("div");
                const div5 = document.createElement("div");
                const button1 = document.createElement("button");
                const a2 = document.createElement("a");
                const button2 = document.createElement("button");
                const button3 = document.createElement("button");

                img.src = song.thumbnail;
                li.dataset.id = song.id;
                li.dataset.url = song.url;
                li.dataset.guild = guild;
                li.dataset.name = song.name;
                li.className = "songli";
                div1.innerText = song.name;
                div1.className = "songtitle";
                div2.innerText = "...";
                div2.style = "color: #5B5B66;";
                div3.className = "songbuttons";
                div4.innerText = song.id + ". - ";
                div4.style = "white-space: pre;";
                div5.className = "duration";
                div5.style = "white-space: pre;";
                div5.innerText = song.duration + "  ";
                button1.innerText = "Play";
                button2.innerText = "Link";
                a2.href = song.url;
                a2.target = "_blank";
                button3.innerText = "Delete";
                button1.className = "songplay";
                button2.className = "songlink";
                button3.className = "songdelete";
                button1.id = "songplay";
                button2.id = "songlink";
                button3.id = "songdelete";

                li.appendChild(div4);
                li.appendChild(img);
                li.appendChild(div2);
                li.appendChild(div1);
                li.appendChild(div5);
                li.appendChild(div3);
                div3.appendChild(button1);
                div3.appendChild(a2);
                a2.appendChild(button2);
                div3.appendChild(button3);

                sortlist.appendChild(li);

                if (index === 0) {
                    li.draggable = false;
                    li.style = "background-color: #5B5B66;";
                    var firstname = song.name;
                    var firstthumb = song.thumbnail;
                    firstthumb = firstthumb.replace(
                        "mqdefault",
                        "maxresdefault",
                    );
                    document.getElementById("first").innerHTML = firstname;
                    document.getElementById("firstthumb").src = firstthumb;
                }
                button1.addEventListener("click", async () => {
                    const response = await fetch("/play_song", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({
                            id: song.id,
                            url: song.url,
                            guild: guild,
                        }),
                    });
                    const data = await response.json();
                    console.log(data);
                    fetchData();
                });
                button3.addEventListener("click", async () => {
                    const response = await fetch("/delete_song", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({
                            id: song.id,
                            url: song.url,
                            guild: guild,
                        }),
                    });
                    const data = await response.json();
                    console.log(data);
                    fetchData();
                });
                li.addEventListener("dragend", async () => {
                    const updatedListJSON = getUpdatedListJSON();
                    const response = await fetch("/update_list", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: updatedListJSON,
                        guild: guild,
                    });
                    const data = await response.json();
                    console.log(data);
                    fetchData();
                });
            });
            const pllengthdiv = document.getElementById("pllength");
            pllengthdiv.dataset.pllength = pllength;
            pllengthdiv.innerText = pllength + " songs in queue";
            slist(sortlist);
        });
}

