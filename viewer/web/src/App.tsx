import { BrowserRouter, Routes, Route } from "react-router-dom";
import LibraryPage from "@/pages/LibraryPage";
import ViewerPage from "@/pages/ViewerPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LibraryPage />} />
        <Route path="/view/:id" element={<ViewerPage />} />
      </Routes>
    </BrowserRouter>
  );
}
