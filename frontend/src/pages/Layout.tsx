import Header from "@/components/home/Header";
import {Outlet} from "react-router-dom";

export const Layout = () => {
  return (
    <div className="h-[100vh] w-[100vw]">
      <Header />
      <Outlet />
    </div>
  );
};
