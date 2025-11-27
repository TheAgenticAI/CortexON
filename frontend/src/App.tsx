import {BrowserRouter, Route, Routes} from "react-router-dom";
import Home from "./pages/Home";
import {Layout} from "./pages/Layout";
import {Vault} from "./pages/Vault";
import {ConversationProvider} from "./contexts/ConversationContext";

function App() {
  return (
    <ConversationProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="/vault" element={<Vault />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConversationProvider>
  );
}

export default App;
