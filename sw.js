var CACHE='stitchrow-v4';
var FILES=['./','./index.html','./manifest.webmanifest','./icon.svg','./icon-192.png','./icon-512.png','./sw.js','./server.html'];
self.addEventListener('install',function(e){e.waitUntil(caches.open(CACHE).then(function(c){return c.addAll(FILES);}).then(function(){return self.skipWaiting();}));});
self.addEventListener('activate',function(e){e.waitUntil(caches.keys().then(function(k){return Promise.all(k.filter(function(x){return x!==CACHE;}).map(function(x){return caches.delete(x);}));}).then(function(){return self.clients.claim();}));});
self.addEventListener('fetch',function(e){if(e.request.method!=='GET')return;e.respondWith(caches.match(e.request).then(function(hit){return hit||fetch(e.request).then(function(res){if(res&&res.ok){var c=res.clone();caches.open(CACHE).then(function(k){k.put(e.request,c);});}return res;}).catch(function(){return caches.match('./index.html');});}));});
